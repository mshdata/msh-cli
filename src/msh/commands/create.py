import click
import os

@click.group()
def create() -> None:
    """Create new assets or resources."""
    pass

@create.command()
@click.argument('asset_name')
def asset(asset_name: str) -> None:
    """Creates a new production-ready asset template."""
    cwd = os.getcwd()
    models_dir = os.path.join(cwd, "models")
    
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)
        
    file_path = os.path.join(models_dir, f"{asset_name}.msh")
    
    if os.path.exists(file_path):
        click.echo(f"[bold red]Error: Asset '{asset_name}' already exists at {file_path}[/bold red]")
        return

    # Template with f-string formatting
    # We need to be careful with braces. 
    # {asset_name} is replaced.
    # {{ source }} should appear as {{ source }} in the file -> {{{{ source }}}} in f-string.
    # ${SOURCES...} should appear as ${SOURCES...} -> ${{SOURCES...}} in f-string.
    
    template = f"""/* --- CONFIG ---
name: {asset_name}
description: Ingests and prepares {asset_name} data.

# 1. Core Lifecycle
deployment:
  mode: blue_green

# 2. Incremental Logic (Ready for production append/merge)
incremental:
  strategy: append
  cursor_field: updated_at

# 3. Source (Connects to a database/API via .env)
ingest:
  type: sql_database # Change this to rest_api if needed
  credentials: ${{SOURCES__PROD_DB__CREDENTIALS}}
  table: source_{asset_name}_table

# 4. Data Quality Contracts (Runs before deployment)
tests:
  - not_null: id
  - unique: id

# 5. Lineage Exposure
expose:
  - type: dashboard
    name: {asset_name}_dashboard
    url: https://mshdata.io/docs
--- */

-- Your transformation logic starts here.

SELECT
    id,
    -- Add your transformation logic here
    updated_at
FROM {{{{ source }}}}
"""

    with open(file_path, "w") as f:
        f.write(template)
        
    from rich.console import Console
    console = Console()
    console.print(f"[bold green][OK] Created new asset: models/{asset_name}.msh[/bold green]")
