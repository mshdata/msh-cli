"""
Asset command group for consistent command structure.

Provides aliases like `msh asset run`, `msh asset rollback`, etc.
"""
import click
from msh.commands.run import run, rollback, freshness, preview
from msh.commands.state import status, versions
from msh.commands.sample import sample


@click.group()
def asset() -> click.Group:
    """Asset management commands."""
    pass


# Register subcommands as aliases
asset.add_command(run, name="run")
asset.add_command(rollback, name="rollback")
asset.add_command(freshness, name="freshness")
asset.add_command(preview, name="preview")
asset.add_command(status, name="status")
asset.add_command(versions, name="versions")
asset.add_command(sample, name="sample")

