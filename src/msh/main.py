import click
from typing import Any
from msh.commands.init import init, generate
from msh.commands.run import run, rollback, freshness, preview
from msh.commands.doctor import doctor
from msh.commands.ui import ui, lineage
from msh.commands.plan import plan
from msh.commands.state import versions, status
from msh.commands.fmt import fmt
from msh.commands.validate import validate
from msh.commands.create import create
from msh.commands.publish import publish
from msh.commands.discover import discover
from msh.commands.sample import sample
from msh.commands.asset import asset

@click.group()
def cli() -> click.Group:
    """The msh Data Platform."""
    pass

# Register commands
cli.add_command(init)
cli.add_command(generate)
cli.add_command(discover)
cli.add_command(sample)
cli.add_command(asset)  # Asset command group (aliases)
cli.add_command(run)
cli.add_command(preview)
cli.add_command(rollback)
cli.add_command(freshness)
cli.add_command(doctor)
cli.add_command(ui)
cli.add_command(lineage)
cli.add_command(plan)
cli.add_command(versions)
cli.add_command(status)
cli.add_command(fmt)
cli.add_command(validate)
cli.add_command(create)
cli.add_command(publish)

if __name__ == "__main__":
    cli()