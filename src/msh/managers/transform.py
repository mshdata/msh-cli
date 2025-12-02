"""
Transform manager module for msh.

Handles the transformation phase, testing, Blue/Green swaps, and cleanup.
"""
import os
import json
import subprocess
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from rich.table import Table
from rich import box
from sqlalchemy import text
from sqlalchemy.engine import Engine

from msh.logger import logger as console
from msh_engine.lifecycle import cleanup_junk, StateManager
from msh_engine.sql_utils import (
    safe_identifier, safe_schema_name, execute_ddl_safe, SQLSecurityError
)
from msh_engine.db_utils import transaction_context


class TransformManager:
    """Manages the transformation phase of the pipeline."""
    
    def __init__(
        self, 
        engine: Engine, 
        dry_run: bool, 
        debug: bool, 
        deploy: bool, 
        target_schema: str,
        raw_dataset: str,
        build_dir: str,
        env: str,
        state_manager: StateManager,
        cwd: Optional[str] = None
    ) -> None:
        """
        Initialize the transform manager.
        
        Args:
            engine: SQLAlchemy engine for database connections
            dry_run: Whether to run in dry-run mode
            debug: Whether to show debug output
            deploy: Whether to deploy (swap views)
            target_schema: Target schema name
            raw_dataset: Name of the raw dataset
            build_dir: Build directory for dbt artifacts
            env: Environment name (e.g., 'dev', 'prod')
            state_manager: StateManager instance for tracking deployments
        """
        self.engine: Engine = engine
        self.dry_run: bool = dry_run
        self.debug: bool = debug
        self.deploy: bool = deploy
        self.target_schema: str = target_schema
        self.raw_dataset: str = raw_dataset
        self.build_dir: str = build_dir
        self.env: str = env
        self.state_manager: StateManager = state_manager
        # Store cwd for reliable project root calculation
        self.cwd: str = cwd or os.path.dirname(os.path.dirname(build_dir)) if build_dir.endswith(os.path.join(".msh", "build")) else os.path.dirname(build_dir)

    def run_phase(self, execution_plan: List[Dict[str, Any]]) -> None:
        """
        Runs the transformation phase for all assets in the execution plan.
        
        Args:
            execution_plan: List of asset metadata dictionaries
        """
        # 1. Identify models to run
        models_to_run = []
        assets_map = {} # Map model_name -> asset dict

        for asset in execution_plan:
            name = asset["name"]
            model_name = asset["model_name"]
            content_hash = asset["hash"]
            active_hash = asset.get("active_hash")
            
            assets_map[name] = asset
            
            if active_hash == content_hash:
                if self.dry_run:
                    console.print(f"[bold yellow][Dry Run] {name}: No changes detected (Incremental).[/bold yellow]")
                else:
                    console.print(f"[bold green]No code change detected for {name}. Queuing Incremental Append.[/bold green]")
                models_to_run.append(name)
            else:
                if self.dry_run:
                    console.print(f"[bold yellow][Dry Run] {name}: Code change detected (Blue/Green).[/bold yellow]")
                else:
                    console.print(f"[bold blue]Code change detected for {name}. Queuing Blue/Green Deploy.[/bold blue]")
                models_to_run.append(name)

        if not models_to_run:
            console.print("[bold blue]No transformations to run.[/bold blue]")
            return

        if self.dry_run:
            console.print(f"[bold yellow][Dry Run] Would batch run dbt for: {', '.join(models_to_run)}[/bold yellow]")
            return

        # 2. Batch Run dbt
        console.print(f"[bold blue]Batching dbt run for {len(models_to_run)} models...[/bold blue]")
        select_str = " ".join(models_to_run)
        
        try:
            self._run_dbt(select_str)
            console.print(f"[bold green][OK] Batch transformation complete.[/bold green]")
        except subprocess.CalledProcessError:
            console.print(f"[bold red][ERROR][/bold red] Transform: Batch transformation failed. Aborting phase.")
            return

        # 3. Post-Run: Tests, Swap, Janitor
        for name in models_to_run:
            asset = assets_map[name]
            name = asset["name"]
            raw_table = asset["raw_table"]
            content_hash = asset["hash"]
            active_hash = asset.get("active_hash")
            model_name = asset["model_name"]
            
            # Tests
            if asset.get("quality") or asset.get("tests"):
                console.print(f"[bold blue]Running Quality Tests for {name}...[/bold blue]")
                try:
                    self._run_dbt_test(name)
                    console.print(f"[bold green][OK] Quality Tests passed.[/bold green]")
                except subprocess.CalledProcessError:
                    console.print(f"[bold red][ERROR][/bold red] Transform: Quality Tests failed for '{name}'. Aborting deployment for this asset.")
                    # Cleanup failed Blue/Green model with proper transaction management
                    try:
                        with transaction_context(self.engine) as conn:
                            try:
                                execute_ddl_safe(
                                    conn,
                                    "DROP TABLE IF EXISTS :schema.:identifier",
                                    schema=self.target_schema,
                                    identifier=model_name
                                )
                            except SQLSecurityError as e:
                                console.print(f"[yellow]Warning: Could not safely drop table {model_name}: {e}[/yellow]")
                            
                            try:
                                execute_ddl_safe(
                                    conn,
                                    "DROP VIEW IF EXISTS :schema.:identifier",
                                    schema=self.target_schema,
                                    identifier=model_name
                                )
                            except SQLSecurityError as e:
                                console.print(f"[yellow]Warning: Could not safely drop view {model_name}: {e}[/yellow]")
                            
                            if active_hash != content_hash:
                                try:
                                    execute_ddl_safe(
                                        conn,
                                        "DROP TABLE IF EXISTS :schema.:identifier",
                                        schema=self.raw_dataset,
                                        identifier=raw_table
                                    )
                                except SQLSecurityError as e:
                                    console.print(f"[yellow]Warning: Could not safely drop raw table {raw_table}: {e}[/yellow]")
                    except Exception as e:
                        console.print(f"[yellow]Warning: Cleanup failed: {e}[/yellow]")
                    continue

            # Swap
            if active_hash != content_hash:
                if self.deploy:
                    self._swap_asset(name, model_name, active_hash)
                else:
                    console.print(f"[bold green][OK] Preview Ready for {name}.[/bold green]")
                    console.print(f"[dim][..] Raw Data: {raw_table}[/dim]")
                    console.print(f"[dim][..] Model Data: {model_name}[/dim]")
            else:
                 console.print(f"[bold green][OK] {name} updated (Incremental).[/bold green]")

            # Janitor
            if self.deploy:
                self._janitor_cleanup(name, content_hash)

    def _run_dbt(self, select: str) -> None:
        """
        Runs dbt run command.
        
        Args:
            select: Model selection string
        """
        with console.status(f"[bold blue][..] Weaving data (Transform phase)...[/bold blue]", spinner="line"):
            try:
                dbt_args = ["dbt", "run", "--select", select, "--project-dir", self.build_dir, "--profiles-dir", self.build_dir, "--target", self.env]
                if not self.debug:
                    # Suppress dbt's own output in normal mode
                    dbt_args.append("--quiet")
                subprocess.run(
                    dbt_args,
                    check=True,
                    capture_output=not self.debug
                )
            except subprocess.CalledProcessError as e:
                console.print(f"[bold red][ERROR][/bold red] Transform: Transformation failed for '{select}'")
                if self.debug:
                    console.print(f"[dim]Return code: {e.returncode}[/dim]")
                    if e.stdout:
                        console.print(f"[dim]dbt stdout:[/dim]\n{e.stdout.decode()}")
                    if e.stderr:
                        console.print(f"[dim]dbt stderr:[/dim]\n{e.stderr.decode()}")
                    if not e.stdout and not e.stderr:
                        console.print(f"[dim]Error details: {str(e)}[/dim]")
                elif not self.debug:
                    # Extract meaningful error from stderr if possible
                    stderr_text = e.stderr.decode() if e.stderr else ""
                    if "Compilation Error" in stderr_text or e.returncode == 2:
                        console.print("[bold red][ERROR][/bold red] Transform: Compilation Error. Check your SQL references.")
                    else:
                        console.print("[bold red][ERROR][/bold red] Transform: Transformation failed. Run with --debug for details.")
                raise e

    def _parse_test_results(self, build_dir: str, asset_name: str) -> Optional[Dict[str, Any]]:
        """
        Parse dbt run_results.json to extract test results.
        
        Args:
            build_dir: Build directory containing dbt artifacts
            asset_name: Asset name to filter tests for
            
        Returns:
            Dictionary with test results or None if parsing fails
        """
        run_results_path = os.path.join(build_dir, "target", "run_results.json")
        if not os.path.exists(run_results_path):
            return None
        
        try:
            with open(run_results_path, "r") as f:
                run_results = json.load(f)
            
            # Extract test results for this asset
            tests = []
            results = run_results.get("results", [])
            
            for result in results:
                # Filter by asset name (test name typically includes asset name)
                test_name = result.get("unique_id", "")
                if asset_name in test_name or test_name.startswith(f"test.{asset_name}"):
                    status = "pass" if result.get("status") == "pass" else "fail"
                    execution_time = result.get("execution_time", 0)
                    tests.append({
                        "name": result.get("unique_id", "").split(".")[-1] if "." in test_name else test_name,
                        "status": status,
                        "execution_time": execution_time
                    })
            
            if not tests:
                return None
            
            passed = sum(1 for t in tests if t["status"] == "pass")
            failed = len(tests) - passed
            
            return {
                "asset_name": asset_name,
                "timestamp": datetime.now().isoformat(),
                "tests": tests,
                "summary": {
                    "total": len(tests),
                    "passed": passed,
                    "failed": failed
                }
            }
        except (json.JSONDecodeError, IOError, OSError) as e:
            console.debug(f"Failed to parse test results: {e}")
            return None
    
    def _save_test_results(self, asset_name: str, results: Dict[str, Any]) -> None:
        """
        Save test results to .msh/test_results.json.
        
        Args:
            asset_name: Asset name
            results: Test results dictionary
        """
        # Use stored cwd for reliable project root
        test_results_dir = os.path.join(self.cwd, ".msh")
        test_results_file = os.path.join(test_results_dir, "test_results.json")
        
        # Ensure directory exists
        os.makedirs(test_results_dir, exist_ok=True)
        
        # Load existing results or create new dict
        all_results = {}
        if os.path.exists(test_results_file):
            try:
                with open(test_results_file, "r") as f:
                    all_results = json.load(f)
            except (json.JSONDecodeError, IOError, OSError):
                all_results = {}
        
        # Update with new results
        all_results[asset_name] = results
        
        # Save back to file
        try:
            with open(test_results_file, "w") as f:
                json.dump(all_results, f, indent=2)
        except (IOError, OSError) as e:
            console.debug(f"Failed to save test results: {e}")

    def _run_dbt_test(self, select: str) -> None:
        """
        Runs dbt test command and captures test results.
        
        Args:
            select: Model selection string (asset name)
            
        Raises:
            subprocess.CalledProcessError: If tests fail, raises exception to stop deployment
        """
        try:
            dbt_args = ["dbt", "test", "--select", select, "--project-dir", self.build_dir, "--profiles-dir", self.build_dir, "--target", self.env]
            if not self.debug:
                # Suppress dbt's own output in normal mode
                dbt_args.append("--quiet")
            subprocess.run(
                dbt_args,
                check=True,
                capture_output=not self.debug
            )
            
            # Parse and save test results on success
            test_results = self._parse_test_results(self.build_dir, select)
            if test_results:
                self._save_test_results(select, test_results)
                
        except subprocess.CalledProcessError as e:
            # Try to parse results even on failure (some tests may have passed)
            test_results = self._parse_test_results(self.build_dir, select)
            if test_results:
                self._save_test_results(select, test_results)
            
            console.print(f"[bold red][ERROR][/bold red] Transform: Data Quality Tests failed for '{select}'")
            if self.debug:
                console.print(f"[dim]Return code: {e.returncode}[/dim]")
                if e.stdout:
                    console.print(f"[dim]dbt stdout:[/dim]\n{e.stdout.decode()}")
                if e.stderr:
                    console.print(f"[dim]dbt stderr:[/dim]\n{e.stderr.decode()}")
                if not e.stdout and not e.stderr:
                    console.print(f"[dim]Error details: {str(e)}[/dim]")
            elif not self.debug:
                # Extract meaningful error from stderr if possible
                stderr_text = e.stderr.decode() if e.stderr else ""
                if "Compilation Error" in stderr_text or e.returncode == 2:
                    console.print("[bold red][ERROR][/bold red] Transform: Test Compilation Error. Check your SQL references.")
                else:
                    console.print("[bold red][ERROR][/bold red] Transform: Data Quality Tests failed. Run with --debug for details.")
            # Re-raise to stop deployment phase
            raise e

    def _swap_asset(self, name: str, model_name: str, active_hash: Optional[str]) -> None:
        """
        Performs Blue/Green swap by creating/updating view.
        
        Args:
            name: Asset name
            model_name: Model table name (versioned)
            active_hash: Previous active hash (for state tracking)
        """
        # Security Check - validate identifiers
        try:
            safe_identifier(name, "asset")
            safe_identifier(model_name, "model")
            safe_schema_name(self.target_schema)
        except SQLSecurityError as e:
            console.print(f"[bold red]Security Error: Invalid identifier: {e}[/bold red]")
            return

        try:
            # Use transaction context for atomic operation
            with transaction_context(self.engine) as conn:
                # Drop existing view/table if they exist
                try:
                    execute_ddl_safe(
                        conn,
                        "DROP VIEW IF EXISTS :schema.:identifier",
                        schema=self.target_schema,
                        identifier=name
                    )
                except (SQLSecurityError, Exception):
                    # Ignore errors - view might not exist
                    pass
                
                try:
                    execute_ddl_safe(
                        conn,
                        "DROP TABLE IF EXISTS :schema.:identifier",
                        schema=self.target_schema,
                        identifier=name
                    )
                except (SQLSecurityError, Exception):
                    # Ignore errors - table might not exist
                    pass
                
                # Create view pointing to the new model
                # Note: We've validated all identifiers, so this is safe
                query = (
                    f"CREATE OR REPLACE VIEW {self.target_schema}.{name} "
                    f"AS SELECT * FROM {self.target_schema}.{model_name}"
                )
                conn.execute(text(query))
                # Transaction will auto-commit on successful exit
                
            console.print(f"[bold green][OK] Asset '{name}' deployed.[/bold green]")

            # Save deployment state (outside transaction)
            if active_hash:
                state_dict = {
                    "asset": name,
                    "previous_hash": active_hash,
                    "timestamp": time.time(),
                    "env": self.env
                }
                self.state_manager.save_deployment_state(state_dict)
        except SQLSecurityError as e:
            console.print(f"[bold red][ERROR][/bold red] Transform: Security validation failed for swap: {e}")
        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Transform: Swap failed for '{name}': {e}")

    def _janitor_cleanup(self, name: str, content_hash: str) -> None:
        """
        Cleans up old versions of assets.
        
        Args:
            name: Asset name
            content_hash: Current content hash
        """
        # Use transaction context for atomic cleanup
        try:
            with transaction_context(self.engine) as conn:
                dropped_items = cleanup_junk(conn, name, content_hash, self.target_schema, self.raw_dataset)
                # Transaction will auto-commit on successful exit
                
            if dropped_items:
                table = Table(title=f"Janitor Cleanup ({name})", box=box.ASCII)
                table.add_column("Schema", style="cyan")
                table.add_column("Object", style="magenta")
                table.add_column("Type", style="green")
                for schema, obj, type_ in dropped_items:
                    table.add_row(schema, obj, type_)
                console.print(table)
        except Exception as e:
            console.print(f"[yellow]Warning: Janitor cleanup failed for {name}: {e}[/yellow]")

