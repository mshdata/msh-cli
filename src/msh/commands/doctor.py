import click
import os
import subprocess
from rich.table import Table
from rich import box
from msh.logger import logger as console

@click.command()
def doctor() -> None:
    """Checks the health of the msh environment."""
    table = Table(title="msh Doctor", box=box.SIMPLE)
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="dim")
    
    # 1. Python Version
    import sys
    py_ver = sys.version.split()[0]
    if sys.version_info >= (3, 9):
        table.add_row("Python Version", "[green]OK[/green]", f"{py_ver} >= 3.9")
    else:
        table.add_row("Python Version", "[red]FAIL[/red]", f"{py_ver} < 3.9")
        
    # 2. dbt Installed
    try:
        subprocess.run(["dbt", "--version"], check=True, capture_output=True)
        table.add_row("dbt Installed", "[green]OK[/green]", "Found dbt executable")
    except Exception:
        table.add_row("dbt Installed", "[red]FAIL[/red]", "dbt not found in PATH")
        
    # 3. dlt Importable
    try:
        import dlt
        table.add_row("dlt Library", "[green]OK[/green]", f"v{dlt.__version__}")
    except ImportError:
        table.add_row("dlt Library", "[red]FAIL[/red]", "Not installed")
        
    # 4. .env exists
    if os.path.exists(".env"):
        table.add_row(".env File", "[green]OK[/green]", "Found")
    else:
        table.add_row(".env File", "[yellow]WARN[/yellow]", "Missing (using defaults?)")
        
    # 5. Write Permissions
    try:
        test_file = ".msh_write_test"
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        table.add_row("Write Access", "[green]OK[/green]", "Current directory is writable")
    except Exception:
        table.add_row("Write Access", "[red]FAIL[/red]", "Cannot write to current directory")
        
    console.print(table)
