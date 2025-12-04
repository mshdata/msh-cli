"""
msh ai explain command handler.

Uses AI to explain what an asset does.
"""
import os
import json
import click
from typing import Optional
from rich.console import Console
from msh.ai.context_pack import ContextPackGenerator
from msh.ai.providers import get_provider
from msh.ai.prompts import get_explain_prompt
from msh.ai.config import AIConfig
from msh.logger import logger


def explain_asset(asset_path: str, output_json: bool = False) -> None:
    """
    Explain an asset using AI.
    
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
        
        # Generate context pack
        context_gen = ContextPackGenerator(project_root=project_root)
        
        # Extract asset ID from path
        asset_id = os.path.splitext(os.path.basename(asset_path))[0]
        
        context_pack = context_gen.generate_context_pack(asset_id=asset_id)
        
        # Generate prompt
        prompt = get_explain_prompt(context_pack, asset_id)
        
        # Call AI
        console.print("[yellow]Calling AI...[/yellow]")
        response = provider.call(prompt)
        
        # Parse response (try JSON first, fallback to text)
        try:
            explanation = json.loads(response)
        except json.JSONDecodeError:
            # Not JSON, treat as text
            explanation = {
                "summary": response,
                "grain": "unknown",
                "upstream_assets": [],
                "downstream_assets": [],
                "business_terms": [],
                "policies": []
            }
        
        # Output
        if output_json:
            explanation["asset_id"] = asset_id
            console.print(json.dumps(explanation, indent=2))
        else:
            console.print(f"\n[bold green]Explanation for {asset_id}[/bold green]")
            console.print(f"\n{explanation.get('summary', 'No summary available')}")
            
            grain = explanation.get("grain")
            if grain:
                console.print(f"\n[bold]Data Grain:[/bold] {grain}")
            
            upstream = explanation.get("upstream_assets", [])
            if upstream:
                console.print(f"\n[bold]Upstream:[/bold] {', '.join(upstream)}")
            
            downstream = explanation.get("downstream_assets", [])
            if downstream:
                console.print(f"\n[bold]Downstream:[/bold] {', '.join(downstream)}")
            
            terms = explanation.get("business_terms", [])
            if terms:
                console.print(f"\n[bold]Business Terms:[/bold] {', '.join(terms)}")
    
    except Exception as e:
        logger.error(f"AI Explain: Failed to explain asset: {e}")
        raise click.ClickException(str(e))

