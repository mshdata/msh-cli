"""
msh config command.

Configure AI provider and model for msh.
"""
import os
import click
from rich.console import Console
from msh.ai.config import AIConfig
from msh.logger import logger


@click.group()
def config() -> None:
    """Configure msh settings."""
    pass


@config.command()
@click.option("--provider", help="AI provider key (e.g., openai, anthropic, ollama)")
@click.option("--model", help="Model identifier (e.g., gpt-4.5, claude-3-opus)")
@click.option("--api-key", help="API key or env:VAR_NAME reference")
@click.option("--endpoint", help="Optional custom endpoint URL")
def ai(provider: str, model: str, api_key: str, endpoint: str) -> None:
    """
    Configure AI provider and model for msh.
    
    Configuration is saved to ~/.msh/config (global) or msh.yaml (project-level).
    """
    console = Console()
    
    try:
        project_root = os.getcwd()
        ai_config = AIConfig(project_root=project_root)
        
        # Save configuration
        ai_config.save_global(
            provider=provider,
            model=model,
            api_key=api_key,
            endpoint=endpoint
        )
        
        console.print(f"\n[bold green]AI configuration updated[/bold green]")
        
        # Validate
        if ai_config.validate():
            config_data = ai_config.load()
            console.print(f"Provider: {config_data.get('provider', 'not set')}")
            console.print(f"Model: {config_data.get('model', 'not set')}")
            console.print(f"Endpoint: {config_data.get('endpoint', 'default')}")
            console.print(f"\nConfiguration saved to: {ai_config.GLOBAL_CONFIG_PATH}")
        else:
            console.print("[yellow]Warning: Configuration incomplete[/yellow]")
    
    except Exception as e:
        logger.error(f"Config: Failed to configure AI: {e}")
        raise click.ClickException(str(e))


# Register config command group
cli = click.CommandCollection(sources=[config])

