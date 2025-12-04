"""
msh ai fix command handler.

Uses AI to suggest fixes for broken assets.
"""
import os
import json
import click
from typing import Optional
from rich.console import Console
from msh.ai.context_pack import ContextPackGenerator
from msh.ai.providers import get_provider
from msh.ai.prompts import get_fix_prompt
from msh.ai.config import AIConfig
from msh.ai.patch import PatchEngine
from msh.logger import logger


def fix_asset(
    asset_path: str,
    apply: bool = False,
    output_json: bool = False,
    error_message: Optional[str] = None
) -> None:
    """
    Fix an asset using AI.
    
    Args:
        asset_path: Path to the .msh file
        apply: If True, apply patch after confirmation
        output_json: Whether to output JSON
        error_message: Optional error message from failed run
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
        
        context_pack = context_gen.generate_context_pack(asset_id=asset_id)
        
        # Generate prompt
        prompt = get_fix_prompt(context_pack, asset_id, error_message)
        
        # Call AI
        console.print("[yellow]Analyzing asset with AI...[/yellow]")
        response = provider.call(prompt)
        
        # Parse response (try JSON first)
        try:
            patch_response = json.loads(response)
        except json.JSONDecodeError:
            # Not JSON, create a simple patch structure
            patch_response = {
                "patches": [{
                    "file_path": asset_path,
                    "diff": response,
                    "operations": []
                }]
            }
        
        # Output
        if output_json:
            patch_response["asset_id"] = asset_id
            console.print(json.dumps(patch_response, indent=2))
        else:
            console.print(f"\n[bold green]Fix suggestions for {asset_id}[/bold green]")
            
            patches = patch_response.get("patches", [])
            for patch in patches:
                file_path = patch.get("file_path", asset_path)
                diff = patch.get("diff", "")
                operations = patch.get("operations", [])
                
                console.print(f"\n[bold]File:[/bold] {file_path}")
                if diff:
                    console.print(f"\n[bold]Diff:[/bold]")
                    console.print(diff)
                if operations:
                    console.print(f"\n[bold]Operations:[/bold] {len(operations)}")
                    for op in operations[:5]:  # Show first 5
                        op_type = op.get("op", "unknown")
                        path = op.get("path", "")
                        console.print(f"  - {op_type} at {path}")
            
            if apply:
                # Apply patch
                patch_engine = PatchEngine()
                results = patch_engine.apply_patch(
                    patch_data=patch_response,
                    dry_run=False
                )
                console.print(f"\n[bold green]Patch applied successfully[/bold green]")
                console.print(f"Applied to: {len(results['applied'])} file(s)")
            else:
                console.print(f"\n[yellow]Use --apply to apply these fixes.[/yellow]")
    
    except Exception as e:
        logger.error(f"AI Fix: Failed to fix asset: {e}")
        raise click.ClickException(str(e))

