"""
msh ai review command handler.

Uses AI to review an asset for risks and issues.
"""
import os
import json
import click
from typing import Optional
from rich.console import Console
from msh.ai.context_pack import ContextPackGenerator
from msh.ai.providers import get_provider
from msh.ai.prompts import get_review_prompt
from msh.ai.config import AIConfig
from msh.logger import logger


def review_asset(asset_path: str, output_json: bool = False) -> None:
    """
    Review an asset using AI.
    
    Args:
        asset_path: Path to the .msh file
        output_json: Whether to output JSON
    """
    console = Console()
    
    try:
        # Load AI config
        project_root = os.path.dirname(os.path.abspath(asset_path))
        ai_config = AIConfig(project_root=project_root)
        
        if not ai_config.validate():
            raise click.ClickException("AI configuration incomplete. Run 'msh config ai' first.")
        
        # Get provider
        provider = get_provider(project_root=project_root)
        
        # Generate context pack (include tests and glossary)
        context_gen = ContextPackGenerator(project_root=project_root)
        
        # Extract asset ID from path
        asset_id = os.path.splitext(os.path.basename(asset_path))[0]
        
        context_pack = context_gen.generate_context_pack(
            asset_id=asset_id,
            include_tests=True
        )
        
        # Generate prompt
        prompt = get_review_prompt(context_pack, asset_id)
        
        # Call AI
        console.print("[yellow]Reviewing asset with AI...[/yellow]")
        response = provider.call(prompt)
        
        # Parse response (try JSON first, fallback to text)
        try:
            review = json.loads(response)
        except json.JSONDecodeError:
            # Not JSON, treat as text summary
            review = {
                "summary": response,
                "risks": [],
                "glossary_issues": [],
                "performance_notes": [],
                "suggested_changes": []
            }
        
        # Output
        if output_json:
            review["asset_id"] = asset_id
            console.print(json.dumps(review, indent=2))
        else:
            console.print(f"\n[bold green]Review for {asset_id}[/bold green]")
            console.print(f"\n{review.get('summary', 'No summary available')}")
            
            risks = review.get("risks", [])
            if risks:
                console.print(f"\n[bold red]Risks:[/bold red]")
                for risk in risks:
                    console.print(f"  - {risk}")
            
            glossary_issues = review.get("glossary_issues", [])
            if glossary_issues:
                console.print(f"\n[bold yellow]Glossary Issues:[/bold yellow]")
                for issue in glossary_issues:
                    console.print(f"  - {issue}")
            
            performance_notes = review.get("performance_notes", [])
            if performance_notes:
                console.print(f"\n[bold cyan]Performance Notes:[/bold cyan]")
                for note in performance_notes:
                    console.print(f"  - {note}")
            
            suggested_changes = review.get("suggested_changes", [])
            if suggested_changes:
                console.print(f"\n[bold green]Suggested Changes:[/bold green]")
                for change in suggested_changes:
                    change_type = change.get("type", "unknown")
                    description = change.get("description", "")
                    console.print(f"  - [{change_type}] {description}")
    
    except Exception as e:
        logger.error(f"AI Review: Failed to review asset: {e}")
        raise click.ClickException(str(e))

