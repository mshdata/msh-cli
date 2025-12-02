import click
import os
import json
import duckdb
import datetime
from typing import Optional, Dict, Any
from rich.console import Console
from rich.table import Table
from rich import box

import msh_engine.lifecycle
from msh_engine.lifecycle import StateManager
from msh.utils.config import load_msh_config, get_destination_credentials
from msh_engine.db_utils import get_connection_engine

console = Console()

@click.command()
@click.argument('asset_name')
def versions(asset_name: str) -> None:
    """Show deployment history for an asset."""
    cwd = os.getcwd()
    
    # Load config for destination
    msh_config = load_msh_config(cwd)
    target_destination = msh_config.get("destination", "duckdb")
    creds = get_destination_credentials(target_destination, cwd)

    # Use StateManager to get asset history
    state_manager = StateManager(destination=target_destination, credentials=creds)
    history = state_manager.get_asset_history(asset_name)
    
    if not history:
        console.print(f"[yellow]No history found for asset '{asset_name}'.[/yellow]")
        return
        
    table = Table(title=f"Versions: {asset_name}", box=box.SIMPLE)
    table.add_column("Hash", style="cyan")
    table.add_column("Deployed At", style="magenta")
    table.add_column("Status", style="green")
    
    for entry in history:
        ts = datetime.datetime.fromtimestamp(entry["timestamp"]).strftime('%Y-%m-%d %H:%M:%S')
        table.add_row(entry["hash"], ts, entry["status"])
        
    console.print(table)

@click.command()
@click.option('--format', 'output_format', type=click.Choice(['table', 'json'], case_sensitive=False), default='table', help='Output format: table or json.')
def status(output_format: str) -> None:
    """Show current active version for all assets."""
    cwd = os.getcwd()
    
    msh_config = load_msh_config(cwd)
    target_destination = msh_config.get("destination", "duckdb")
    creds = get_destination_credentials(target_destination, cwd)
    
    engine = get_connection_engine(target_destination, credentials=creds)
    
    try:
        with engine.connect() as conn:
            project_status = msh_engine.lifecycle.get_project_status(conn)
            
            if not project_status:
                if output_format.lower() == 'json':
                    console.print(json.dumps({"assets": []}, indent=2))
                else:
                    console.print("[yellow]No active assets found.[/yellow]")
                return
                
            if output_format.lower() == 'json':
                # Output as JSON
                result = {
                    "assets": [
                        {"name": name, "active_hash": hash_}
                        for name, hash_ in project_status.items()
                    ]
                }
                console.print(json.dumps(result, indent=2))
            else:
                # Output as table (default)
                table = Table(title="Project Status", box=box.SIMPLE)
                table.add_column("Asset", style="bold white")
                table.add_column("Active Hash", style="cyan")
                
                for name, hash_ in project_status.items():
                    table.add_row(name, hash_)
                    
                console.print(table)
        
    finally:
        if hasattr(engine, 'dispose'):
            engine.dispose()
