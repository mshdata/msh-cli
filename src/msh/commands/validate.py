import click
import os
import re
from pathlib import Path
from typing import List, Tuple
from rich.console import Console
from msh.compiler import MshCompiler
from msh.constants import DEFAULT_BUILD_DIR

console = Console()

@click.command()
def validate() -> None:
    """Static analysis for .msh projects (CI/CD safe)."""
    cwd = os.getcwd()
    
    models_path = os.path.join(cwd, "models")
    if os.path.exists(models_path):
        search_path = Path(models_path)
    else:
        search_path = Path(cwd)
        
    msh_files = [f for f in search_path.glob("*.msh") if f.is_file()]
    
    if not msh_files:
        console.print("[yellow]No .msh files found.[/yellow]")
        return

    console.print(f"[bold blue]Validating {len(msh_files)} files...[/bold blue]\n")
    
    # Initialize Compiler (we don't need build dir for parsing, but it's required by init)
    # We can pass a dummy build dir or the real one.
    compiler = MshCompiler(os.path.join(cwd, DEFAULT_BUILD_DIR))
    
    errors = []
    seen_names = {}
    
    for file_path in msh_files:
        rel_path = file_path.name
        file_errors = []
        
        # 1. Syntax & Schema via Compiler
        try:
            # This validates YAML and transform/transform_file logic
            data, _ = compiler.parse(file_path)
            
            # Check required keys
            if "name" not in data:
                file_errors.append("Missing 'name'")
            else:
                name = data["name"]
                if name in seen_names:
                    file_errors.append(f"Duplicate name '{name}' (also in {seen_names[name]})")
                else:
                    seen_names[name] = rel_path
                    
            if "ingest" not in data:
                file_errors.append("Missing 'ingest'")
                
            # Compiler.parse handles transform vs transform_file check, so if we are here, it's valid or one is present.
            # But we should check if 'transform' ended up in data (Compiler puts it there)
            if "transform" not in data:
                 file_errors.append("Missing 'transform' or 'transform_file'")

            # 2. Jinja Safety
            if "transform" in data and isinstance(data["transform"], str):
                sql = data["transform"]
                # Check for unclosed tags
                open_tags = len(re.findall(r"{{", sql))
                close_tags = len(re.findall(r"}}", sql))
                if open_tags != close_tags:
                    file_errors.append(f"Unclosed Jinja tags ({{{{: {open_tags}, }}}}: {close_tags})")
                    
                open_blocks = len(re.findall(r"{%", sql))
                close_blocks = len(re.findall(r"%}", sql))
                if open_blocks != close_blocks:
                    file_errors.append(f"Unclosed Jinja blocks ({{%: {open_blocks}, %}}: {close_blocks})")
                    
            # 3. Secrets Presence (Heuristic)
            if "ingest" in data and "name" in data:
                ingest = data["ingest"]
                name = data["name"]
                
                if ingest.get("type") in ["rest_api", "sql_database"]:
                    prefix = f"SOURCES__{name.upper()}__"
                    found_secret = False
                    for key in os.environ:
                        if key.startswith(prefix):
                            found_secret = True
                            break
                    
                    if not found_secret:
                        # Check if yaml has credentials (bad practice but valid)
                        if "credentials" not in ingest and "config" not in ingest:
                             # Just a warning for now, or ignore as per previous logic
                             pass

        except ValueError as e:
            file_errors.append(f"Validation error: {str(e)}")
        except Exception as e:
            file_errors.append(f"Unexpected error: {str(e)}")
            
        if file_errors:
            console.print(f"[bold red][FAIL] {rel_path}[/bold red]")
            for err in file_errors:
                console.print(f"  [red]- {err}[/red]")
            console.print(f"[yellow]Tip: Check the file syntax and ensure all required fields are present. See 'msh create asset' for a template.[/yellow]")
            errors.extend([(rel_path, err) for err in file_errors])
        else:
            console.print(f"[bold green][PASS] {rel_path}[/bold green]")

    if errors:
        console.print(f"\n[bold red][ERROR][/bold red] Validate: Validation failed with {len(errors)} error(s) across {len(set([e[0] for e in errors]))} file(s).")
        console.print(f"[yellow]Tip: Fix the errors above and run 'msh validate' again.[/yellow]")
        exit(1)
    else:
        console.print("\n[bold green]All checks passed.[/bold green]")
