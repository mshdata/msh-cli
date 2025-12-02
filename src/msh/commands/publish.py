import click
from msh_engine.lifecycle import get_active_hash
from msh_engine.db_utils import get_connection_engine
from msh_engine.export import export_asset

@click.command()
@click.argument("asset_name")
@click.option("--to", "target", required=True, help="The target destination (e.g., salesforce, hubspot).")
def publish(asset_name: str, target: str) -> None:
    """
    Publish an asset to an external destination.
    """
    click.echo(f"Publishing {asset_name} to {target}...")
    
    # 1. Get active hash
    # We need a connection to the DWH to check the active hash
    # Assuming 'duckdb' is the main DWH for metadata checking as well
    conn_engine = get_connection_engine("duckdb")
    
    with conn_engine.connect() as conn:
        active_hash = get_active_hash(conn, asset_name)
        
        if not active_hash:
            click.echo(f"Error: Could not find active hash for asset '{asset_name}'. Is it deployed?")
            return

        # 2. Construct active table name
        # The convention seems to be model_{asset_name}_{hash}
        # But let's check if get_active_hash returns just the hash.
        # Yes, lifecycle.py says: "Returns the hash string (e.g., "1a8c")"
        # And the view definition is: CREATE VIEW revenue AS SELECT * FROM main.model_revenue_1a8c;
        # So the table name is model_{asset_name}_{active_hash}
        # We should probably respect the schema too, but export_asset takes table name.
        # Let's assume 'main' schema or let the query handle it if it's in the search path.
        # Ideally we pass "main.model_{asset_name}_{active_hash}"
        
        active_table_name = f"model_{asset_name}_{active_hash}"
        click.echo(f"Found active table: {active_table_name}")
        
        # 3. Export
        try:
            export_asset(asset_name, active_table_name, target)
        except Exception as e:
            click.echo(f"Failed to publish: {e}")
            # We don't raise here to keep CLI clean, but we could exit with error code.
            exit(1)
