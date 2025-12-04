"""
msh ai tests command handler.

Uses AI to generate or improve tests for an asset.
"""
import os
import json
import click
from typing import Optional
from rich.console import Console
from msh.ai.context_pack import ContextPackGenerator
from msh.ai.providers import get_provider
from msh.ai.prompts import get_tests_prompt
from msh.ai.config import AIConfig
from msh.ai.patch import PatchEngine
from msh.logger import logger


def generate_tests(
    asset_path: str,
    apply: bool = False,
    output_json: bool = False
) -> None:
    """
    Generate or improve tests for an asset using AI.
    
    Args:
        asset_path: Path to the .msh file
        apply: If True, apply test changes
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
        
        # Generate context pack
        context_gen = ContextPackGenerator(project_root=project_root)
        
        # Extract asset ID from path
        asset_id = os.path.splitext(os.path.basename(asset_path))[0]
        
        context_pack = context_gen.generate_context_pack(
            asset_id=asset_id,
            include_tests=True
        )
        
        # Generate prompt
        prompt = get_tests_prompt(context_pack, asset_id)
        
        # Call AI
        console.print("[yellow]Generating tests with AI...[/yellow]")
        response = provider.call(prompt)
        
        # Parse response
        try:
            tests_response = json.loads(response)
        except json.JSONDecodeError:
            # Not JSON, create simple structure
            tests_response = {
                "suggested_tests": [response],
                "patch": {
                    "patches": []
                }
            }
        
        # Output
        if output_json:
            tests_response["asset_id"] = asset_id
            console.print(json.dumps(tests_response, indent=2))
        else:
            console.print(f"\n[bold green]Test suggestions for {asset_id}[/bold green]")
            
            suggested_tests = tests_response.get("suggested_tests", [])
            if suggested_tests:
                console.print(f"\n[bold]Suggested Tests:[/bold]")
                for test in suggested_tests:
                    console.print(f"  - {test}")
            
            patch = tests_response.get("patch", {})
            patches = patch.get("patches", [])
            if patches:
                console.print(f"\n[bold]Patch Operations:[/bold] {len(patches)}")
            
            if apply and patches:
                # Apply patch
                patch_engine = PatchEngine()
                results = patch_engine.apply_patch(
                    patch_data={"patches": patches},
                    dry_run=False
                )
                console.print(f"\n[bold green]Tests applied successfully[/bold green]")
                console.print(f"Applied to: {len(results['applied'])} file(s)")
            elif apply:
                console.print(f"\n[yellow]No patch operations to apply.[/yellow]")
            else:
                console.print(f"\n[yellow]Use --apply to apply these test changes.[/yellow]")
    
    except Exception as e:
        logger.error(f"AI Tests: Failed to generate tests: {e}")
        raise click.ClickException(str(e))

