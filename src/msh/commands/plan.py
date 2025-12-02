import click
from msh.orchestrator import Orchestrator

@click.command()
@click.option('--env', default='dev', help='Target environment (dev, prod, etc).')
def plan(env: str) -> None:
    """Generates an execution plan (Dry Run)."""
    # Acts as an alias for msh run --dry-run
    orchestrator = Orchestrator(env, debug=False, dry_run=True, deploy=True)
    orchestrator.run()
