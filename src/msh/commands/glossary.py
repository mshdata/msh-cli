"""
msh glossary command group.

Commands for managing glossary terms, metrics, dimensions, and policies.
"""
import os
import json
import click
from typing import Optional
from rich.console import Console
from msh.glossary.glossary import Glossary
from msh.logger import logger


@click.group()
def glossary() -> None:
    """Manage glossary terms, metrics, dimensions, and policies."""
    pass


@glossary.command()
@click.argument("name")
@click.option("--description", help="Description of the term")
@click.option("--id", "term_id", help="Optional explicit ID (e.g., term.customer)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def add_term(name: str, description: Optional[str], term_id: Optional[str], output_json: bool) -> None:
    """
    Create a new glossary term in the project glossary file.
    
    NAME: Name of the business term
    """
    console = Console()
    
    try:
        project_root = os.getcwd()
        glossary_obj = Glossary(project_root=project_root)
        
        term = glossary_obj.add_term(
            name=name,
            description=description,
            term_id=term_id
        )
        
        if output_json:
            console.print(json.dumps(term, indent=2))
        else:
            console.print(f"\n[bold green]Term added successfully[/bold green]")
            console.print(f"ID: {term['id']}")
            console.print(f"Name: {term['name']}")
            if term.get("description"):
                console.print(f"Description: {term['description']}")
    
    except ValueError as e:
        logger.error(f"Glossary: {e}")
        raise click.ClickException(str(e))
    except Exception as e:
        logger.error(f"Glossary: Failed to add term: {e}")
        raise click.ClickException(str(e))


@glossary.command()
@click.argument("term_name_or_id")
@click.option("--asset", required=True, help="Asset ID or path")
@click.option("--column", help="Column name within the asset (optional)")
@click.option("--role", help="Role of the column (e.g., primary_key, foreign_key, attribute)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def link_term(
    term_name_or_id: str,
    asset: str,
    column: Optional[str],
    role: Optional[str],
    output_json: bool
) -> None:
    """
    Link an existing glossary term to assets and columns.
    
    TERM_NAME_OR_ID: Name or ID of the glossary term
    """
    console = Console()
    
    try:
        project_root = os.getcwd()
        glossary_obj = Glossary(project_root=project_root)
        
        term = glossary_obj.link_term(
            term_name_or_id=term_name_or_id,
            asset=asset,
            column=column,
            role=role
        )
        
        if output_json:
            console.print(json.dumps(term, indent=2))
        else:
            console.print(f"\n[bold green]Term linked successfully[/bold green]")
            console.print(f"Term: {term['name']} ({term['id']})")
            console.print(f"Asset: {asset}")
            if column:
                console.print(f"Column: {column}")
            if role:
                console.print(f"Role: {role}")
    
    except ValueError as e:
        logger.error(f"Glossary: {e}")
        raise click.ClickException(str(e))
    except Exception as e:
        logger.error(f"Glossary: Failed to link term: {e}")
        raise click.ClickException(str(e))


@glossary.command()
@click.option("--json", "output_json", is_flag=True, help="Return glossary as JSON")
def list(output_json: bool) -> None:
    """List glossary terms in the current project."""
    console = Console()
    
    try:
        project_root = os.getcwd()
        glossary_obj = Glossary(project_root=project_root)
        
        glossary_data = glossary_obj.load()
        
        if output_json:
            console.print(json.dumps(glossary_data, indent=2))
        else:
            terms = glossary_data.get("terms", [])
            metrics = glossary_data.get("metrics", [])
            dimensions = glossary_data.get("dimensions", [])
            policies = glossary_data.get("policies", [])
            
            console.print(f"\n[bold cyan]Glossary: {glossary_data.get('project', 'unknown')}[/bold cyan]")
            console.print(f"\n[bold yellow]Terms:[/bold yellow] {len(terms)}")
            for term in terms[:10]:  # Show first 10
                console.print(f"  - {term.get('name', 'unnamed')} ({term.get('id', 'no-id')})")
            if len(terms) > 10:
                console.print(f"  ... ({len(terms) - 10} more)")
            
            console.print(f"\n[bold yellow]Metrics:[/bold yellow] {len(metrics)}")
            console.print(f"\n[bold yellow]Dimensions:[/bold yellow] {len(dimensions)}")
            console.print(f"\n[bold yellow]Policies:[/bold yellow] {len(policies)}")
    
    except Exception as e:
        logger.error(f"Glossary: Failed to list glossary: {e}")
        raise click.ClickException(str(e))


@glossary.command()
@click.option("--path", help="Optional output file path; otherwise print to stdout")
def export(path: Optional[str]) -> None:
    """Export the full glossary as JSON for AI or external tools."""
    console = Console()
    
    try:
        project_root = os.getcwd()
        glossary_obj = Glossary(project_root=project_root)
        
        glossary_data = glossary_obj.load()
        
        output = json.dumps(glossary_data, indent=2)
        
        if path:
            with open(path, "w") as f:
                f.write(output)
            console.print(f"\n[bold green]Glossary exported to: {path}[/bold green]")
        else:
            console.print(output)
    
    except Exception as e:
        logger.error(f"Glossary: Failed to export glossary: {e}")
        raise click.ClickException(str(e))


# Register glossary command group
cli = click.CommandCollection(sources=[glossary])

