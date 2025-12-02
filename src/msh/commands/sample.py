"""
Sample command for previewing data from assets.

Provides quick data preview and sampling capabilities for testing and iteration.
"""
import os
import click
from typing import Optional, List, Dict, Any, Tuple
from rich.table import Table
from rich import box
from sqlalchemy import text
from sqlalchemy.engine import Engine

from msh.logger import logger as console
from msh.compiler import MshCompiler
from msh_engine.db_utils import get_connection_engine, transaction_context
from msh_engine.lifecycle import get_active_hash, check_table_exists
from msh_engine.sql_utils import safe_identifier, safe_schema_name, SQLSecurityError
from msh.utils.config import load_msh_config, get_target_schema, get_raw_dataset, get_destination_credentials


def _get_table_name(
    asset_name: str,
    env: str,
    source_type: str,
    cwd: str,
    msh_config: Dict[str, Any],
    engine: Engine
) -> Optional[Tuple[str, str]]:
    """
    Resolve table name from asset name.
    
    Args:
        asset_name: Name of the asset
        env: Environment name
        source_type: 'raw' or 'model'
        cwd: Current working directory
        msh_config: Configuration dictionary
        engine: Database engine
        
    Returns:
        Tuple of (table_name, schema_name) or None if not found
    """
    try:
        safe_identifier(asset_name, "asset")
    except SQLSecurityError as e:
        console.print(f"[bold red][ERROR][/bold red] Sample: Invalid asset name: {e}")
        return None
    
    dest = msh_config.get("destination", "duckdb")
    target_schema = get_target_schema(dest, msh_config, env)
    raw_dataset = get_raw_dataset(msh_config, env)
    
    with engine.connect() as conn:
        if source_type == "raw":
            # Get active hash to find the raw table
            active_hash = get_active_hash(conn, asset_name, target_schema)
            if not active_hash:
                console.print(f"[yellow]No active version found for asset '{asset_name}'. Asset may not have been deployed yet.[/yellow]")
                return None
            
            table_name = f"raw_{asset_name}_{active_hash}"
            return (table_name, raw_dataset)
        
        elif source_type == "model":
            # Get active hash to find the model table
            active_hash = get_active_hash(conn, asset_name, target_schema)
            if not active_hash:
                console.print(f"[yellow]No active version found for asset '{asset_name}'. Asset may not have been deployed yet.[/yellow]")
                return None
            
            table_name = f"model_{asset_name}_{active_hash}"
            return (table_name, target_schema)
        
        else:
            # Try view first (most common case)
            if check_table_exists(conn, asset_name, target_schema):
                return (asset_name, target_schema)
            
            # Fallback: try to find any table matching the asset name
            console.print(f"[yellow]Asset '{asset_name}' not found. Run 'msh run {asset_name}' first.[/yellow]")
            return None


def _query_sample(
    engine: Engine,
    table_name: str,
    schema: str,
    limit: int
) -> Optional[List[Dict[str, Any]]]:
    """
    Execute SELECT query with LIMIT to get sample data.
    
    Args:
        engine: Database engine
        table_name: Name of the table
        schema: Schema name
        limit: Number of rows to return
        
    Returns:
        List of dictionaries representing rows, or None on error
    """
    try:
        safe_identifier(table_name, "table")
        safe_schema_name(schema)
        safe_identifier(str(limit), "limit")
    except SQLSecurityError as e:
        console.print(f"[bold red][ERROR][/bold red] Sample: Invalid input: {e}")
        return None
    
    try:
        # Construct safe query with quoted identifiers
        query = text(f'SELECT * FROM "{schema}"."{table_name}" LIMIT :limit')
        
        with engine.connect() as conn:
            result = conn.execute(query, {"limit": limit})
            rows = []
            for row in result:
                # Convert row to dictionary
                row_dict = {}
                for key, value in row._mapping.items():
                    # Handle None values and long strings
                    if value is None:
                        row_dict[key] = None
                    elif isinstance(value, str) and len(value) > 100:
                        row_dict[key] = value[:100] + "..."
                    else:
                        row_dict[key] = value
                rows.append(row_dict)
            
            return rows
    except Exception as e:
        console.print(f"[bold red][ERROR][/bold red] Sample: Failed to query table: {e}")
        return None


def _get_database_type(engine: Engine) -> str:
    """
    Detect database type from SQLAlchemy engine.
    
    Args:
        engine: SQLAlchemy engine
        
    Returns:
        Database type string ('duckdb', 'postgresql', 'snowflake', 'sqlite', 'unknown')
    """
    try:
        url_str = str(engine.url)
        url_lower = url_str.lower()
        
        if 'duckdb' in url_lower:
            return 'duckdb'
        elif 'postgresql' in url_lower or 'postgres' in url_lower:
            return 'postgresql'
        elif 'snowflake' in url_lower:
            return 'snowflake'
        elif 'sqlite' in url_lower:
            return 'sqlite'
        elif 'mysql' in url_lower or 'mariadb' in url_lower:
            return 'mysql'
        else:
            return 'unknown'
    except (AttributeError, ValueError) as e:
        console.debug(f"Failed to detect database type: {e}")
        return 'unknown'


def _create_sample_table(
    engine: Engine,
    source_table: str,
    source_schema: str,
    sample_table: str,
    target_schema: str,
    size: int
) -> bool:
    """
    Create a temporary sample table for testing.
    
    Supports multiple database types with appropriate sampling syntax.
    
    Args:
        engine: Database engine
        source_table: Source table name
        source_schema: Source schema name
        sample_table: Name for the sample table
        target_schema: Target schema name
        size: Number of rows to sample
        
    Returns:
        True if successful, False otherwise
    """
    try:
        safe_identifier(source_table, "table")
        safe_schema_name(source_schema)
        safe_identifier(sample_table, "table")
        safe_schema_name(target_schema)
        safe_identifier(str(size), "size")
    except SQLSecurityError as e:
        console.print(f"[bold red][ERROR][/bold red] Sample: Invalid input: {e}")
        return False
    
    # Detect database type
    db_type = _get_database_type(engine)
    
    try:
        # Build query based on database type
        if db_type == 'duckdb':
            # DuckDB: USING SAMPLE {size}
            query = text(
                f'CREATE TABLE "{target_schema}"."{sample_table}" '
                f'AS SELECT * FROM "{source_schema}"."{source_table}" USING SAMPLE {size}'
            )
        elif db_type == 'postgresql':
            # PostgreSQL: ORDER BY RANDOM() LIMIT {size}
            query = text(
                f'CREATE TABLE "{target_schema}"."{sample_table}" '
                f'AS SELECT * FROM "{source_schema}"."{source_table}" '
                f'ORDER BY RANDOM() LIMIT :size'
            )
        elif db_type == 'snowflake':
            # Snowflake: TABLESAMPLE ({size} ROWS)
            query = text(
                f'CREATE TABLE "{target_schema}"."{sample_table}" '
                f'AS SELECT * FROM "{source_schema}"."{source_table}" '
                f'TABLESAMPLE ({size} ROWS)'
            )
        elif db_type == 'sqlite':
            # SQLite: ORDER BY RANDOM() LIMIT {size}
            query = text(
                f'CREATE TABLE "{target_schema}"."{sample_table}" '
                f'AS SELECT * FROM "{source_schema}"."{source_table}" '
                f'ORDER BY RANDOM() LIMIT :size'
            )
        elif db_type == 'mysql':
            # MySQL/MariaDB: ORDER BY RAND() LIMIT {size}
            query = text(
                f'CREATE TABLE `{target_schema}`.`{sample_table}` '
                f'AS SELECT * FROM `{source_schema}`.`{source_table}` '
                f'ORDER BY RAND() LIMIT :size'
            )
        else:
            console.print(f"[yellow]Sampling not supported for database type '{db_type}'. Use --limit instead.[/yellow]")
            console.print(f"[dim]Supported databases: DuckDB, PostgreSQL, Snowflake, SQLite, MySQL[/dim]")
            return False
        
        # Use transaction_context for atomic DDL operation
        with transaction_context(engine) as conn:
            # Execute with parameters for databases that need them
            if db_type in ['postgresql', 'sqlite', 'mysql']:
                conn.execute(query, {"size": size})
            else:
                conn.execute(query)
            # Transaction auto-commits on successful exit
        
        console.print(f"[bold green][OK] Created sample table '{target_schema}.{sample_table}' with {size} rows (using {db_type} syntax).[/bold green]")
        return True
    except Exception as e:
        console.print(f"[bold red][ERROR][/bold red] Sample: Failed to create sample table: {e}")
        if db_type == 'unknown':
            console.print(f"[yellow]Tip: Database type detection failed. Try using --limit instead of --size.[/yellow]")
        return False


@click.command()
@click.argument('asset_name', required=True)
@click.option('--limit', default=10, help='Number of rows to preview (default: 10).')
@click.option('--size', type=int, help='Create a sample table with this many rows for testing.')
@click.option('--env', default='dev', help='Environment to query (default: dev).')
@click.option('--source', type=click.Choice(['raw', 'model', 'view'], case_sensitive=False), 
              default='view', help='Source to sample from: raw table, model table, or view (default: view).')
def sample(asset_name: str, limit: int, size: Optional[int], env: str, source: str) -> None:
    """
    Preview or sample data from an asset.
    
    Examples:
    
    \b
        # Preview 10 rows from the view (default)
        msh sample orders
        
    \b
        # Preview 20 rows from the raw table
        msh sample orders --limit 20 --source raw
        
    \b
        # Create a sample table with 1000 rows for testing
        msh sample orders --size 1000
    
    The command queries the active version of the asset. If the asset hasn't been
    deployed yet, you'll need to run 'msh run <asset_name>' first.
    """
    cwd = os.getcwd()
    
    # Load config
    msh_config = load_msh_config(cwd)
    if not msh_config:
        console.print("[bold red][ERROR][/bold red] Sample: No msh.yaml found. Run 'msh init' first.")
        return
    
    dest = msh_config.get("destination", "duckdb")
    creds = get_destination_credentials(dest, cwd)
    
    # Connect to database
    try:
        engine = get_connection_engine(dest, credentials=creds)
    except Exception as e:
        console.print(f"[bold red][ERROR][/bold red] Sample: Failed to connect to database: {e}")
        return
    
    # Get table name
    table_info = _get_table_name(asset_name, env, source.lower(), cwd, msh_config, engine)
    if not table_info:
        return
    
    table_name, schema = table_info
    
    # If --size is specified, create sample table
    if size:
        sample_table_name = f"{asset_name}_sample_{size}"
        if _create_sample_table(engine, table_name, schema, sample_table_name, schema, size):
            console.print(f"[bold cyan]Sample table created: {schema}.{sample_table_name}[/bold cyan]")
            console.print(f"[dim]You can now query this table or use it for testing.[/dim]")
        return
    
    # Otherwise, preview data
    rows = _query_sample(engine, table_name, schema, limit)
    if rows is None:
        return
    
    if not rows:
        console.print(f"[yellow]No rows found in table '{schema}.{table_name}'.[/yellow]")
        return
    
    # Display results in a table
    if rows:
        table = Table(title=f"Sample from {asset_name} ({schema}.{table_name})", box=box.ROUNDED)
        
        # Add columns based on first row
        for col_name in rows[0].keys():
            table.add_column(col_name, overflow="fold")
        
        # Add rows
        for row in rows:
            table.add_row(*[str(row.get(col, "")) for col in rows[0].keys()])
        
        console.print(table)
        console.print(f"[dim]Showing {len(rows)} row(s). Use --limit to change.[/dim]")

