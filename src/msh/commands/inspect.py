"""
msh inspect command.

Parses a .msh asset into structured AST + metadata for AI consumption.
"""
import os
import json
import click
from pathlib import Path
from typing import Optional, Dict, Any
from rich.console import Console
from rich.json import JSON
from msh.ai.metadata import MetadataExtractor
from msh.utils.config import load_msh_config
from msh.logger import logger


@click.command()
@click.argument("asset_path", type=click.Path(exists=True, readable=True))
@click.option("--json", "output_json", is_flag=True, help="Output structured JSON instead of human-readable text")
def inspect(asset_path: str, output_json: bool) -> None:
    """
    Parse a .msh asset into structured AST + metadata.
    
    ASSET_PATH: Path to the .msh file to inspect
    """
    console = Console()
    
    try:
        # Load msh config
        project_root = os.path.dirname(os.path.abspath(asset_path))
        msh_config = load_msh_config(project_root)
        
        # Extract metadata
        extractor = MetadataExtractor(msh_config=msh_config)
        metadata = extractor.extract_asset_metadata(asset_path, project_root)
        
        if output_json:
            # Output as JSON
            console.print(json.dumps(metadata, indent=2))
        else:
            # Output human-readable format
            _print_human_readable(console, metadata)
    
    except Exception as e:
        logger.error(f"Inspect: Failed to inspect {asset_path}: {e}")
        raise click.ClickException(str(e))


def _print_human_readable(console: Console, metadata: Dict[str, Any]) -> None:
    """Print metadata in human-readable format."""
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    
    # Asset info
    console.print(f"\n[bold cyan]Asset:[/bold cyan] {metadata['id']}")
    console.print(f"[bold cyan]Path:[/bold cyan] {metadata['path']}")
    console.print(f"[bold cyan]Content Hash:[/bold cyan] {metadata.get('content_hash', 'N/A')}")
    
    # Blocks
    blocks = metadata.get("blocks", {})
    if blocks:
        console.print("\n[bold yellow]Blocks:[/bold yellow]")
        if "ingest" in blocks:
            ingest = blocks["ingest"]
            console.print(f"  [green]Ingest:[/green] {ingest.get('type', 'unknown')}")
            if ingest.get("source"):
                console.print(f"    Source: {ingest['source']}")
            if ingest.get("table"):
                console.print(f"    Table: {ingest['table']}")
            if ingest.get("resource"):
                console.print(f"    Resource: {ingest['resource']}")
        
        if "transform" in blocks:
            transform = blocks["transform"]
            deps = transform.get("dependencies", [])
            if deps:
                console.print(f"  [green]Transform:[/green] Dependencies: {', '.join(deps)}")
            else:
                console.print(f"  [green]Transform:[/green] No dependencies")
        
        if "contract" in blocks:
            console.print(f"  [green]Contract:[/green] {blocks['contract']}")
    
    # Schema
    schema = metadata.get("schema", {})
    columns = schema.get("columns", [])
    if columns:
        console.print(f"\n[bold yellow]Schema:[/bold yellow] {len(columns)} columns")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Name")
        table.add_column("Type")
        table.add_column("Description")
        
        for col in columns[:10]:  # Show first 10 columns
            table.add_row(
                col.get("name", ""),
                col.get("type", "unknown"),
                col.get("description", "")[:50] or "-"
            )
        
        if len(columns) > 10:
            table.add_row("...", "...", f"({len(columns) - 10} more columns)")
        
        console.print(table)
    
    # Tests
    tests = metadata.get("tests", [])
    if tests:
        console.print(f"\n[bold yellow]Tests:[/bold yellow] {len(tests)} test(s)")
        for test in tests:
            test_name = test.get("name", "unnamed")
            test_type = test.get("type", "unknown")
            console.print(f"  - {test_name} ({test_type})")
    
    # Lineage
    lineage = metadata.get("lineage", {})
    upstream = lineage.get("upstream", [])
    if upstream:
        console.print(f"\n[bold yellow]Upstream Dependencies:[/bold yellow] {', '.join(upstream)}")
    
    console.print()

