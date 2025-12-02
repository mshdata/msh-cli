import click
import os
import yaml
import re
from pathlib import Path
from typing import Any
from rich.console import Console

console = Console()

# --- YAML Customization for Block Literals ---
class LiteralScalarString(str):
    pass

def literal_scalar_representer(dumper: yaml.Dumper, data: LiteralScalarString) -> yaml.ScalarNode:
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

# Register the representer for our custom class
yaml.add_representer(LiteralScalarString, literal_scalar_representer)

class IndentDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(IndentDumper, self).increase_indent(flow, False)

# --- Logic ---

def format_yaml_first(file_path: Path) -> bool:
    """Formats a standard YAML-First .msh file."""
    with open(file_path, "r") as f:
        content = f.read()
        
    try:
        data = yaml.safe_load(content)
    except Exception as e:
        console.print(f"[red]Invalid YAML in {file_path.name}: {e}[/red]")
        return False

    if not data:
        return False

    # Preserve SQL formatting by using block literal style
    if "transform" in data and isinstance(data["transform"], str):
        # Strip and ensure single newline at end
        clean_sql = data["transform"].strip() + "\n"
        data["transform"] = LiteralScalarString(clean_sql)

    with open(file_path, "w") as f:
        yaml.dump(data, f, Dumper=IndentDumper, default_flow_style=False, sort_keys=False, indent=2)
        
    return True

def format_sql_first(file_path: Path) -> bool:
    """Formats a SQL-First .msh file (Frontmatter)."""
    with open(file_path, "r") as f:
        content = f.read()
        
    # Regex to extract Frontmatter
    # Matches /* --- CONFIG --- ... --- */
    pattern = r"^/\* --- CONFIG ---\n(.*?)\n--- \*/\n(.*)$"
    match = re.match(pattern, content, re.DOTALL)
    
    if not match:
        console.print(f"[yellow]Skipping {file_path.name}: Could not parse Frontmatter.[/yellow]")
        return False
        
    yaml_text = match.group(1)
    sql_body = match.group(2)
    
    # Parse YAML to ensure validity and normalize
    try:
        data = yaml.safe_load(yaml_text)
    except Exception as e:
        console.print(f"[red]Invalid YAML in Frontmatter of {file_path.name}: {e}[/red]")
        return False
        
    # Dump YAML back to string
    # We don't use LiteralScalarString here because we are inside a comment block, 
    # and typically the config doesn't have big multi-line strings (except maybe description).
    formatted_yaml = yaml.dump(data, Dumper=IndentDumper, default_flow_style=False, sort_keys=False, indent=2).strip()
    
    # Reconstruct file
    new_content = f"/* --- CONFIG ---\n{formatted_yaml}\n--- */\n{sql_body}"
    
    with open(file_path, "w") as f:
        f.write(new_content)
        
    return True

@click.command()
def fmt() -> None:
    """Formats .msh files (Standard Indentation)."""
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
        
    count = 0
    for file_path in msh_files:
        try:
            # Detect format
            with open(file_path, "r") as f:
                first_line = f.readline()
                
            if first_line.startswith("/* --- CONFIG ---"):
                if format_sql_first(file_path):
                    count += 1
            else:
                if format_yaml_first(file_path):
                    count += 1
                    
        except Exception as e:
            console.print(f"[red]Failed to format {file_path.name}: {e}[/red]")
            
    console.print(f"[bold green][OK] Formatted {count} files.[/bold green]")
