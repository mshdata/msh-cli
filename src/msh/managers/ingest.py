"""
Ingest manager module for msh.

Handles the ingestion phase of the pipeline.
"""
import os
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
from sqlalchemy.engine import Engine

from msh.logger import logger as console
from msh_engine.lifecycle import get_active_hash
from msh.constants import DEFAULT_DUCKDB_PATH


class IngestManager:
    """Manages the ingestion phase of the pipeline."""
    
    def __init__(
        self, 
        engine: Engine, 
        threads: int, 
        dry_run: bool, 
        debug: bool, 
        raw_dataset: str, 
        dest: str, 
        cwd: str, 
        build_dir: str, 
        env: str, 
        target_schema: str
    ) -> None:
        """
        Initialize the ingest manager.
        
        Args:
            engine: SQLAlchemy engine for database connections
            threads: Number of parallel ingestion threads
            dry_run: Whether to run in dry-run mode
            debug: Whether to show debug output
            raw_dataset: Name of the raw dataset
            dest: Destination type (e.g., 'duckdb', 'snowflake')
            cwd: Current working directory
            build_dir: Build directory for dbt artifacts
            env: Environment name (e.g., 'dev', 'prod')
            target_schema: Target schema name
        """
        self.engine: Engine = engine
        self.threads: int = threads
        self.dry_run: bool = dry_run
        self.debug: bool = debug
        self.raw_dataset: str = raw_dataset
        self.dest: str = dest
        self.cwd: str = cwd
        self.build_dir: str = build_dir
        self.env: str = env
        self.target_schema: str = target_schema

    def run_phase(self, execution_plan: List[Dict[str, Any]]) -> None:
        """
        Runs the ingestion phase for all assets in the execution plan.
        
        Args:
            execution_plan: List of asset metadata dictionaries
        """
        assets_to_ingest = []
        
        with self.engine.connect() as conn:
            for asset in execution_plan:
                name = asset["name"]
                content_hash = asset["hash"]
                active_hash = get_active_hash(conn, name, self.target_schema)
                asset["active_hash"] = active_hash
                
                if active_hash != content_hash and asset.get("ingest"):
                    assets_to_ingest.append(asset)
                elif active_hash == content_hash and asset.get("ingest"):
                     assets_to_ingest.append(asset)
                
                if self.dry_run and asset.get("ingest"):
                    if asset not in assets_to_ingest:
                        assets_to_ingest.append(asset)
                        
        if assets_to_ingest:
            console.print(f"[bold blue]Starting Ingest Phase ({len(assets_to_ingest)} assets, {self.threads} threads)...[/bold blue]")
            with ThreadPoolExecutor(max_workers=self.threads) as executor:
                futures = [executor.submit(self._ingest_asset, asset) for asset in assets_to_ingest]
                exceptions = []
                for future in futures:
                    try:
                        future.result()
                    except Exception as e:
                        exceptions.append(e)
                        console.print(f"[bold red][ERROR][/bold red] Ingest: Worker failed: {e}")

            if exceptions:
                for i, ex in enumerate(exceptions):
                    console.print(f"[bold red][ERROR][/bold red] Ingest: Error {i+1}/{len(exceptions)}: {ex}")
                raise exceptions[0]
        else:
            console.print("[bold blue]No assets require ingestion.[/bold blue]")

    def _ingest_asset(self, asset: Dict[str, Any]) -> None:
        """
        Ingests a single asset.
        
        Args:
            asset: Asset metadata dictionary
        """
        name = asset["name"]
        content_hash = asset["hash"]
        ingest = asset["ingest"]
        columns = asset["columns"]
        python_code = asset.get("python_code")
        primary_key = asset.get("primary_key")
        write_disposition = asset.get("write_disposition", "replace")
        contract = asset.get("contract")  # Extract contract config
        
        target_raw_table = f"raw_{name}_{content_hash}"
        job_wd = write_disposition
        
        job_config = {
            "destination": self.dest,
            "dataset_name": self.raw_dataset,
            "table_name": target_raw_table,
            "write_disposition": job_wd,
            "columns": columns,
            "python_code": python_code,
            "primary_key": primary_key,
            "contract": contract,  # Pass contract config to engine
            "source": {}
        }
        
        ingest_type = ingest.get("type")
        if ingest_type == "rest_api":
            job_config["source"] = {
                "type": "rest_api",
                "endpoint": ingest.get("endpoint"),
                "resource": ingest.get("resource"),
                "config": ingest.get("config")
            }
        elif ingest_type == "sql_database":
            job_config["source"] = {
                "type": "sql_database",
                "credentials": ingest.get("credentials"),
                "table": ingest.get("table")
            }
        else:
            source_str = ingest.get("source")
            if "." in source_str:
                parts = source_str.rsplit(".", 1)
                module_name = parts[0]
                func_name = parts[1]
            else:
                module_name = f"dlt.sources.{source_str}"
                func_name = f"{source_str}_source"
            
            job_config["source"] = {
                "type": "module",
                "module": module_name,
                "name": func_name,
                "args": {},
                "resource": ingest.get("resource")
            }
            
        env_vars = os.environ.copy()
        env_vars["MSH_JOB_CONFIG"] = json.dumps(job_config)
        env_vars["DESTINATION__DUCKDB__CREDENTIALS"] = f"duckdb:///{os.path.join(self.cwd, DEFAULT_DUCKDB_PATH)}"
        
        if self.dry_run:
             job_config["dry_run"] = True
             env_vars["MSH_JOB_CONFIG"] = json.dumps(job_config)
        
        try:
            dbt_args = ["dbt", "run", "--select", "generic_loader", "--project-dir", self.build_dir, "--profiles-dir", self.build_dir, "--target", self.env]
            if not self.debug:
                # Suppress dbt's own output in normal mode
                dbt_args.append("--quiet")
            subprocess.run(
                dbt_args,
                env=env_vars,
                check=True,
                capture_output=not self.debug
            )
            if self.dry_run:
                console.print(f"[bold yellow][Dry Run] Verified connection for {name}.[/bold yellow]")
            else:
                console.print(f"[bold green][Ingest] {name} complete.[/bold green]")
        except subprocess.CalledProcessError as e:
            if self.debug:
                console.print(f"[bold red][ERROR][/bold red] Ingest: Failed to load '{name}'")
                console.print(f"[dim]Return code: {e.returncode}[/dim]")
                if e.stdout:
                    console.print(f"[dim]dbt stdout:[/dim]\n{e.stdout.decode()}")
                if e.stderr:
                    console.print(f"[dim]dbt stderr:[/dim]\n{e.stderr.decode()}")
                if not e.stdout and not e.stderr:
                    console.print(f"[dim]Error details: {str(e)}[/dim]")
            else:
                # User-friendly error message in normal mode
                stderr_text = e.stderr.decode() if e.stderr else ""
                if "Compilation Error" in stderr_text or e.returncode == 2:
                    console.print(f"[bold red][ERROR][/bold red] Ingest: Compilation Error for '{name}'. Check your SQL references.")
                else:
                    console.print(f"[bold red][ERROR][/bold red] Ingest: Failed to load '{name}'. Run with --debug for details.")
            raise e

