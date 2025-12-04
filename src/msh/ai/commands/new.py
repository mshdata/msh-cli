"""
msh ai new command handler.

Generates a new .msh asset from natural language description.
"""
import os
import json
import yaml
import click
import sys
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt
from msh.ai.context_pack import ContextPackGenerator
from msh.ai.providers import get_provider
from msh.ai.prompts import get_new_asset_prompt
from msh.ai.config import AIConfig
from msh.ai.safety import AISafety
from msh.logger import logger


def new_asset(
    name: Optional[str] = None,
    apply: bool = False,
    output_path: Optional[str] = None
) -> None:
    """
    Generate a new .msh asset from natural language.
    
    Args:
        name: Optional suggested asset name
        apply: If True, write file automatically
        output_path: Optional path to save the file
    """
    console = Console()
    
    try:
        # Load AI config
        project_root = os.getcwd()
        ai_config = AIConfig(project_root=project_root)
        
        if not ai_config.validate():
            raise click.ClickException("AI configuration incomplete. Run 'msh config ai' first.")
        
        # Get provider
        provider = get_provider(project_root=project_root)
        
        # Prompt for description
        console.print("[bold cyan]Describe the asset you want to create:[/bold cyan]")
        console.print("(You can describe what data to ingest, what transformation to perform, etc.)\n")
        
        description = sys.stdin.read() if not sys.stdin.isatty() else Prompt.ask("Description")
        
        if not description.strip():
            raise click.ClickException("Description cannot be empty")
        
        # Generate asset name if not provided
        if not name:
            # Simple name generation from description
            name = description.split()[0].lower().replace(" ", "_")[:50]
        
        # Generate context pack
        context_gen = ContextPackGenerator(project_root=project_root)
        context_pack = context_gen.generate_context_pack()
        
        # Generate prompt
        prompt = get_new_asset_prompt(context_pack, description, name)
        
        # Call AI
        console.print("[yellow]Generating asset with AI...[/yellow]")
        response = provider.call(prompt)
        
        # Extract YAML from response (may be wrapped in markdown code blocks)
        yaml_content = _extract_yaml_from_response(response)
        
        # Validate YAML
        try:
            parsed = yaml.safe_load(yaml_content)
            if not parsed:
                raise ValueError("Generated YAML is empty")
        except yaml.YAMLError as e:
            logger.error(f"Generated YAML is invalid: {e}")
            raise click.ClickException(f"AI generated invalid YAML: {e}")
        
        # Safety check
        safety = AISafety()
        transform = parsed.get("transform", "")
        if isinstance(transform, str):
            is_safe, warnings = safety.validate_sql(transform)
            if not is_safe:
                raise ValueError(f"Generated SQL contains dangerous operations: {warnings}")
            if warnings:
                console.print(f"[yellow]Warnings: {warnings}[/yellow]")
        
        # Determine output path
        if not output_path:
            output_path = os.path.join(project_root, f"{name}.msh")
        
        # Output or save
        if apply:
            with open(output_path, "w") as f:
                f.write(yaml_content)
            console.print(f"\n[bold green]Asset created: {output_path}[/bold green]")
        else:
            console.print(f"\n[bold green]Generated Asset:[/bold green]")
            console.print(f"\n[yellow]File: {output_path}[/yellow]")
            console.print(f"\n{yaml_content}")
            console.print(f"\n[yellow]Use --apply to write this file.[/yellow]")
    
    except Exception as e:
        logger.error(f"AI New: Failed to generate asset: {e}")
        raise click.ClickException(str(e))


def _extract_yaml_from_response(response: str) -> str:
    """
    Extract YAML content from AI response.
    
    May be wrapped in markdown code blocks or have explanations.
    """
    # Try to find YAML in code blocks
    import re
    
    # Look for ```yaml or ``` blocks
    yaml_block = re.search(r"```(?:yaml)?\n(.*?)```", response, re.DOTALL)
    if yaml_block:
        return yaml_block.group(1).strip()
    
    # Look for YAML-like content (starts with key:)
    yaml_match = re.search(r"^(\w+:\s*.*)$", response, re.MULTILINE)
    if yaml_match:
        # Try to extract from first YAML-like line to end
        lines = response.split("\n")
        yaml_start = None
        for i, line in enumerate(lines):
            if re.match(r"^\w+:\s*", line):
                yaml_start = i
                break
        
        if yaml_start is not None:
            return "\n".join(lines[yaml_start:])
    
    # Return as-is
    return response.strip()

