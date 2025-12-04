"""
msh manifest command.

Generate project-level manifest for AI context.
"""
import os
import json
import click
from typing import Optional
from rich.console import Console
from msh.ai.manifest import ManifestGenerator
from msh.logger import logger


@click.command()
@click.option("--json", "output_json", is_flag=True, help="Output manifest as JSON")
@click.option("--update", is_flag=True, help="Update existing manifest instead of regenerating")
def manifest(output_json: bool, update: bool) -> None:
    """
    Generate project-level manifest.json for AI context.
    
    Scans all .msh files in the project and generates a manifest with
    asset metadata, lineage, schemas, and tests.
    """
    console = Console()
    
    try:
        project_root = os.getcwd()
        manifest_gen = ManifestGenerator(project_root=project_root)
        
        # Generate manifest
        manifest_data = manifest_gen.generate_manifest(update=update)
        
        if output_json:
            # Output as JSON
            console.print(json.dumps(manifest_data, indent=2))
        else:
            # Output summary
            console.print(f"\n[bold green]Manifest generated successfully[/bold green]")
            console.print(f"Project: {manifest_data['project']['name']}")
            console.print(f"Assets: {len(manifest_data['assets'])}")
            console.print(f"Generated at: {manifest_data['generated_at']}")
            console.print(f"\nManifest saved to: {os.path.join(project_root, '.msh', 'manifest.json')}")
            
            # Also generate other cache files
            console.print("\n[bold yellow]Generating metadata cache...[/bold yellow]")
            manifest_gen.generate_all()
            console.print("[bold green]Metadata cache generation complete[/bold green]")
    
    except Exception as e:
        logger.error(f"Manifest: Failed to generate manifest: {e}")
        raise click.ClickException(str(e))

