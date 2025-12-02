import click
import os
import json
import shutil
import subprocess
import datetime
import time
from pathlib import Path
from typing import Optional, List
from rich.table import Table
from rich import box
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text

from msh.logger import logger as console
from msh.compiler import MshCompiler
import msh_engine.lifecycle
from msh_engine.db_utils import get_connection_engine, transaction_context
from msh_engine.sql_utils import safe_identifier, safe_schema_name, safe_hash, SQLSecurityError
from msh.utils.config import load_msh_config, get_target_schema, get_destination_credentials

from msh.orchestrator import Orchestrator

def execute_run(
    env: str, 
    debug: bool, 
    dry_run: bool, 
    deploy: bool = True, 
    asset_selector: Optional[str] = None
) -> None:
    """
    Orchestrates the msh run command.
    Delegates to Orchestrator class.
    """
    try:
        orchestrator = Orchestrator(env, debug, dry_run, deploy, asset_selector)
        orchestrator.run()
    except Exception as e:
        console.print(f"[bold red][ERROR][/bold red] Run: Pipeline execution failed: {e}")
        console.print(f"[yellow]Tip: Run with --debug to see detailed error information.[/yellow]")
        if debug:
            import traceback
            traceback.print_exc()
        # Exit with error code
        import sys
        sys.exit(1)

@click.command()
@click.option('--env', default='dev', help='Target environment (dev, prod, etc).')
@click.option('--debug', is_flag=True, help='Enable debug mode to see dbt logs.')
@click.option('--dry-run', is_flag=True, help='Simulate run without moving data.')
@click.option('--all', 'run_all', is_flag=True, help='Run all assets.')
@click.argument('asset_selector', required=False)
def run(env: str, debug: bool, dry_run: bool, run_all: bool, asset_selector: Optional[str]) -> None:
    """Compiles .msh files and runs the stack with Blue/Green deployment.
    
    ASSET_SELECTOR: Optional. Run specific assets.
    - 'asset_name': Run only this asset.
    - '+asset_name': Run asset and all upstreams.
    - 'asset_name+': Run asset and all downstreams.
    
    Use --all to run all assets.
    """
    if run_all and asset_selector:
        console.print("[bold red]Error: Cannot use --all with asset selector. Use one or the other.[/bold red]")
        import sys
        sys.exit(1)
    
    # If --all is set, pass None as selector (which means run all)
    final_selector = None if run_all else asset_selector
    execute_run(env, debug, dry_run, deploy=True, asset_selector=final_selector)

@click.command()
@click.option('--env', default='dev', help='Target environment (dev, prod, etc).')
@click.option('--debug', is_flag=True, help='Enable debug mode to see dbt logs.')
@click.option('--dry-run', is_flag=True, help='Simulate run without moving data.')
def preview(env: str, debug: bool, dry_run: bool) -> None:
    """Runs the pipeline but skips the final deployment (Swap)."""
    execute_run(env, debug, dry_run, deploy=False, asset_selector=None)

def _execute_rollback(asset_list: Optional[List[str]]) -> None:
    """
    Internal function to execute rollback for one or more assets.
    
    Args:
        asset_list: List of asset names to rollback, or None to rollback all assets.
    """
    cwd = os.getcwd()
    
    msh_config = load_msh_config(cwd)
    target_destination = msh_config.get("destination", "duckdb")
    # Rollback uses prod schema (production operation)
    target_schema = get_target_schema(target_destination, msh_config, env="prod")
    creds = get_destination_credentials(target_destination, cwd)

    state_manager = msh_engine.lifecycle.StateManager(destination=target_destination, credentials=creds)
    engine = get_connection_engine(target_destination, credentials=creds)
    
    # Get list of assets to rollback
    if asset_list is None:
        # Get all assets from project status
        with engine.connect() as conn:
            project_status = msh_engine.lifecycle.get_project_status(conn)
            if not project_status:
                console.print("[yellow]No active assets found to rollback.[/yellow]")
                return
            asset_list = list(project_status.keys())
    
    # Rollback each asset
    success_count = 0
    failed_assets = []
    
    for asset_name in asset_list:
        try:
            latest_state = state_manager.get_latest_deployment(asset_name)
            
            if not latest_state:
                console.print(f"[yellow]No history found for asset '{asset_name}'. Skipping.[/yellow]")
                failed_assets.append((asset_name, "No history"))
                continue
                
            previous_hash = latest_state["previous_hash"]
            timestamp = latest_state["timestamp"]
            
            console.print(f"[bold blue]Rolling back '{asset_name}' to version {previous_hash} (from {timestamp})...[/bold blue]")
            
            # Validate inputs
            try:
                safe_identifier(asset_name, "asset")
                safe_hash(previous_hash)
                safe_schema_name(target_schema)
            except SQLSecurityError as e:
                console.print(f"[bold red]Security Error for '{asset_name}': {e}[/bold red]")
                failed_assets.append((asset_name, f"Security error: {e}"))
                continue
            
            # Check if table exists using engine abstraction
            model_name = f"model_{asset_name}_{previous_hash}"
            
            with engine.connect() as conn:
                exists = msh_engine.lifecycle.check_table_exists(conn, model_name, schema=target_schema)
                
                if not exists:
                    console.print(f"[bold red]Backup table '{target_schema}.{model_name}' no longer exists. Cannot rollback '{asset_name}'.[/bold red]")
                    failed_assets.append((asset_name, "Backup table not found"))
                    continue
                    
            # Execute Swap with transaction management
            with transaction_context(engine) as conn:
                # Validate identifiers
                safe_identifier(model_name, "model")
                
                # Create view pointing to the previous version
                query = (
                    f"CREATE OR REPLACE VIEW {target_schema}.{asset_name} "
                    f"AS SELECT * FROM {target_schema}.{model_name}"
                )
                conn.execute(text(query))
                # Transaction will auto-commit on successful exit
                
            console.print(f"[bold green][OK] Rolled back '{asset_name}' to version {previous_hash}.[/bold green]")
            success_count += 1
            
        except SQLSecurityError as e:
            console.print(f"[bold red]Security Error for '{asset_name}': {e}[/bold red]")
            failed_assets.append((asset_name, f"Security error: {e}"))
        except Exception as e:
            console.print(f"[bold red]Rollback failed for '{asset_name}': {e}[/bold red]")
            failed_assets.append((asset_name, str(e)))
    
    # Summary
    total = len(asset_list)
    console.print(f"\n[bold cyan]Rollback Summary: {success_count}/{total} succeeded[/bold cyan]")
    if failed_assets:
        console.print(f"[bold red]Failed assets:[/bold red]")
        for asset_name, error in failed_assets:
            console.print(f"  - {asset_name}: {error}")
        import sys
        sys.exit(1)

@click.command()
@click.option('--all', 'rollback_all', is_flag=True, help='Rollback all assets.')
@click.argument('asset_names', required=False)
def rollback(rollback_all: bool, asset_names: Optional[str]) -> None:
    """Rolls back asset(s) to their previous version(s).
    
    ASSET_NAMES: Asset name(s) to rollback. Can be:
    - Single asset: 'orders'
    - Multiple assets (comma-separated): 'orders,revenue,users'
    
    Use --all to rollback all assets.
    """
    if rollback_all and asset_names:
        console.print("[bold red]Error: Cannot use --all with asset names. Use one or the other.[/bold red]")
        import sys
        sys.exit(1)
    
    if not rollback_all and not asset_names:
        console.print("[bold red][ERROR][/bold red] Rollback: Must specify either --all or asset name(s).")
        console.print("[yellow]Usage examples:[/yellow]")
        console.print("[dim]  msh rollback --all[/dim]")
        console.print("[dim]  msh rollback orders[/dim]")
        console.print("[dim]  msh rollback orders,revenue  # Multiple assets[/dim]")
        import sys
        sys.exit(1)
    
    # Parse asset names
    if rollback_all:
        asset_list = None  # None means all assets
    else:
        # Split comma-separated asset names
        asset_list = [name.strip() for name in asset_names.split(',') if name.strip()]
        if not asset_list:
            console.print("[bold red][ERROR][/bold red] Rollback: No valid asset names provided.")
            console.print("[yellow]Tip: Use 'msh status' to see available assets.[/yellow]")
            import sys
            sys.exit(1)
    
    # Execute rollback for each asset
    _execute_rollback(asset_list)

@click.command()
def freshness() -> None:
    """Checks data freshness against expectations."""
    cwd = os.getcwd()
    
    # We need to parse .msh files to get expectations
    build_dir = os.path.join(cwd, ".msh", "build")
    # Freshness check uses prod schema (production operation)
    compiler = MshCompiler(build_dir, env="prod") 
    
    models_path = os.path.join(cwd, "models")
    if os.path.exists(models_path):
        search_path = Path(models_path)
    else:
        search_path = Path(cwd)
        
    msh_files = [f for f in search_path.glob("*.msh") if f.is_file()]
    
    # Load msh.yaml for destination
    msh_config = load_msh_config(cwd)
    target_destination = msh_config.get("destination", "duckdb")
    creds = get_destination_credentials(target_destination, cwd)
        
    table = Table(title="Data Freshness", box=box.SIMPLE)
    table.add_column("Asset", style="cyan")
    table.add_column("Last Run", style="magenta")
    table.add_column("Status", style="bold")
    
    any_error = False
    
    now = time.time()
    
    for file_path in msh_files:
        try:
            asset_data, _ = compiler.parse(file_path)
            name = asset_data.get("name")
            freshness = asset_data.get("freshness")
            
            if not freshness:
                continue
                
            state_manager = msh_engine.lifecycle.StateManager(destination=target_destination, credentials=creds)
            last_ts = state_manager.get_last_successful_run(name)
            
            if not last_ts:
                table.add_row(name, "Never", "[red]MISSING[/red]")
                any_error = True 
                continue
                
            # Calculate age
            age_seconds = now - last_ts
            age_hours = age_seconds / 3600
            
            # Parse expectations (simple h/m parsing)
            def parse_duration(s):
                s = str(s).lower()
                if s.endswith("h"):
                    return float(s[:-1])
                if s.endswith("m"):
                    return float(s[:-1]) / 60
                if s.endswith("s"):
                    return float(s[:-1]) / 3600
                if s.endswith("d"):
                    return float(s[:-1]) * 24
                return float(s) # assume hours
                
            warn_after = parse_duration(freshness.get("warn_after", "24h"))
            error_after = parse_duration(freshness.get("error_after", "48h"))
            
            status = "[green]OK[/green]"
            if age_hours > error_after:
                status = "[red]ERROR[/red]"
                any_error = True
            elif age_hours > warn_after:
                status = "[yellow]WARN[/yellow]"
                
            table.add_row(name, f"{age_hours:.1f}h ago", status)
            
        except Exception as e:
            console.print(f"[red]Error checking {file_path}: {e}[/red]")
            
    console.print(table)
    
    if any_error:
        exit(1)
