"""
msh ai command group.

AI-powered commands for msh assets.
"""
import os
import json
import click
from typing import Optional
from rich.console import Console
from msh.ai.context_pack import ContextPackGenerator
from msh.ai.commands.explain import explain_asset
from msh.ai.commands.review import review_asset
from msh.ai.commands.new import new_asset
from msh.ai.commands.fix import fix_asset
from msh.ai.commands.tests import generate_tests
from msh.logger import logger


@click.group()
def ai() -> None:
    """AI-powered commands for msh."""
    pass


@ai.command()
@click.option("--asset", type=str, help="Asset ID or file path to focus the context pack on")
@click.option("--json", "output_json", is_flag=True, help="Output context pack as JSON")
@click.option("--include-tests", is_flag=True, help="Include test metadata in the context pack")
@click.option("--include-history", is_flag=True, help="Include recent run/deploy history")
def context(
    asset: Optional[str],
    output_json: bool,
    include_tests: bool,
    include_history: bool
) -> None:
    """
    Generate an AI-ready context pack for a given asset or project scope.
    
    The context pack includes project info, assets, lineage, glossary,
    schemas, tests, metrics, and policies.
    """
    console = Console()
    
    try:
        project_root = os.getcwd()
        generator = ContextPackGenerator(project_root=project_root)
        
        # Generate context pack
        context_pack = generator.generate_context_pack(
            asset_id=asset,
            include_tests=include_tests,
            include_history=include_history
        )
        
        if output_json:
            # Output as JSON
            console.print(json.dumps(context_pack, indent=2))
        else:
            # Output summary
            console.print(f"\n[bold green]Context Pack Generated[/bold green]")
            console.print(f"Project: {context_pack['project'].get('name', 'unknown')}")
            console.print(f"Assets: {len(context_pack.get('assets', []))}")
            console.print(f"Lineage edges: {len(context_pack.get('lineage', []))}")
            
            if include_tests:
                tests = context_pack.get("tests", [])
                console.print(f"Tests: {len(tests)} asset(s) with tests")
            
            glossary_terms = context_pack.get("glossary_terms", [])
            if glossary_terms:
                console.print(f"Glossary terms: {len(glossary_terms)}")
            
            console.print(f"\nContext pack ready for AI consumption.")
            console.print(f"Use --json flag to see full context pack.")
    
    except Exception as e:
        logger.error(f"AI Context: Failed to generate context pack: {e}")
        raise click.ClickException(str(e))


@ai.command()
@click.argument("asset_path", type=click.Path(exists=True, readable=True))
@click.option("--json", "output_json", is_flag=True, help="Return a structured explanation object")
def explain(asset_path: str, output_json: bool) -> None:
    """
    Use AI to explain what an asset does in plain language.
    
    ASSET_PATH: Path to the .msh file being explained
    """
    explain_asset(asset_path, output_json)


@ai.command()
@click.argument("asset_path", type=click.Path(exists=True, readable=True))
@click.option("--json", "output_json", is_flag=True, help="Return a structured review object")
def review(asset_path: str, output_json: bool) -> None:
    """
    Use AI to review an asset for risks, performance issues, and glossary alignment.
    
    ASSET_PATH: Path to the .msh file being reviewed
    """
    review_asset(asset_path, output_json)


@ai.command()
@click.option("--name", help="Suggested asset id/name")
@click.option("--apply", is_flag=True, help="Write the generated asset to disk automatically")
@click.option("--path", "output_path", help="Path to save the new .msh file (if --apply is set)")
def new(name: Optional[str], apply: bool, output_path: Optional[str]) -> None:
    """
    Generate a new .msh asset from a natural language description.
    
    Prompts for a description of the asset to create.
    """
    new_asset(name=name, apply=apply, output_path=output_path)


@ai.command()
@click.argument("asset_path", type=click.Path(exists=True, readable=True))
@click.option("--apply", is_flag=True, help="Apply the suggested patch after user confirmation")
@click.option("--json", "output_json", is_flag=True, help="Return patch as a JSON structure")
@click.option("--error", "error_message", help="Error message from failed run")
def fix(asset_path: str, apply: bool, output_json: bool, error_message: Optional[str]) -> None:
    """
    Use AI to suggest a fix for a broken or failing asset.
    
    ASSET_PATH: Path to the .msh file to fix
    """
    fix_asset(asset_path, apply=apply, output_json=output_json, error_message=error_message)


@ai.command()
@click.argument("asset_path", type=click.Path(exists=True, readable=True))
@click.option("--apply", is_flag=True, help="Apply suggested test changes to the file")
@click.option("--json", "output_json", is_flag=True, help="Return suggested tests as a JSON structure")
def tests(asset_path: str, apply: bool, output_json: bool) -> None:
    """
    Use AI to generate or improve tests for an asset.
    
    ASSET_PATH: Path to the .msh file whose tests should be improved
    """
    generate_tests(asset_path, apply=apply, output_json=output_json)


@ai.command()
@click.argument("patch_file", type=click.Path(exists=True, readable=True))
@click.option("--dry-run", is_flag=True, help="Show diff without modifying any files")
def apply(patch_file: str, dry_run: bool) -> None:
    """
    Apply an AI-generated patch file to one or more .msh assets.
    
    PATCH_FILE: Path to JSON patch file produced by AI
    """
    from msh.ai.patch import PatchEngine
    from rich.console import Console
    
    console = Console()
    
    try:
        patch_engine = PatchEngine()
        results = patch_engine.apply_patch(patch_file, dry_run=dry_run)
        
        if dry_run:
            console.print(f"\n[bold yellow]Dry Run - No files modified[/bold yellow]")
            for diff_info in results.get("diffs", []):
                console.print(f"\n[bold]File:[/bold] {diff_info['file']}")
                console.print(diff_info["diff"])
        else:
            applied = results.get("applied", [])
            failed = results.get("failed", [])
            
            console.print(f"\n[bold green]Patch Applied[/bold green]")
            console.print(f"Applied to: {len(applied)} file(s)")
            for file_path in applied:
                console.print(f"  - {file_path}")
            
            if failed:
                console.print(f"\n[bold red]Failed:[/bold red] {len(failed)} file(s)")
                for fail_info in failed:
                    console.print(f"  - {fail_info['file']}: {fail_info['error']}")
    
    except Exception as e:
        logger.error(f"AI Apply: Failed to apply patch: {e}")
        raise click.ClickException(str(e))


# Register ai command group
cli = click.CommandCollection(sources=[ai])

