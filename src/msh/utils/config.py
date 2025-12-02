"""
Configuration utilities for msh.

Centralizes all configuration loading and schema resolution logic.
"""
import os
import yaml
import re
from pathlib import Path
from typing import Optional, Dict, Any, Union, List

from msh.constants import DEFAULT_DESTINATION, DEFAULT_RAW_DATASET, SCHEMA_MAIN, SCHEMA_PUBLIC
from msh.logger import logger as console
from msh.git_utils import get_sanitized_schema_suffix


def load_msh_config(cwd: Optional[str] = None) -> Dict[str, Any]:
    """
    Loads and parses msh.yaml from the current or specified directory.
    
    Args:
        cwd: Optional working directory. If None, uses os.getcwd().
        
    Returns:
        Dictionary containing parsed configuration, or empty dict if file doesn't exist.
        Returns empty dict on YAML parsing errors (with warning logged).
    """
    if cwd is None:
        cwd = os.getcwd()
    
    config_path = os.path.join(cwd, "msh.yaml")
    
    if not os.path.exists(config_path):
        return {}
    
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f) or {}
            
            # Resolve environment variables in vars section
            if "vars" in config:
                config["vars"] = resolve_env_vars(config["vars"])
            
            return config
    except (yaml.YAMLError, IOError, OSError) as e:
        console.print(f"[yellow]Warning: Could not parse msh.yaml: {e}[/yellow]")
        return {}


def get_target_schema(
    destination: str, 
    config: Optional[Dict[str, Any]] = None,
    env: str = "dev"
) -> str:
    """
    Returns the target schema name based on destination type and config override.
    In dev environment, appends git branch suffix for schema isolation.
    
    Args:
        destination: The destination type (e.g., 'duckdb', 'snowflake', 'postgres')
        config: Optional configuration dict. If provided, checks for 'target_schema' override.
        env: Environment name ('dev' or 'prod'). Defaults to 'dev'.
        
    Returns:
        Schema name string:
        - "main" for DuckDB (or "main_{suffix}" in dev)
        - "PUBLIC" for Snowflake (or "PUBLIC_{suffix}" in dev)
        - "public" for all other destinations (or "public_{suffix}" in dev)
        - Overridden by config['target_schema'] if present
        - In dev environment, suffix is appended based on git branch
    """
    # Check for override in config
    if config and config.get("target_schema"):
        base_schema = config["target_schema"]
    else:
        # Defaults based on destination
        if destination == "duckdb":
            base_schema = SCHEMA_MAIN
        elif destination == "snowflake":
            base_schema = "PUBLIC"
        else:
            base_schema = SCHEMA_PUBLIC
    
    # Apply git-aware suffix in dev environment
    if env == "dev":
        suffix = get_sanitized_schema_suffix()
        # Ensure total length doesn't exceed DB limits (63 chars for most DBs)
        # Leave room for suffix: base + "_" + suffix (max 20) = base + 21
        max_base_length = 63 - 21  # 42 chars for base schema
        if len(base_schema) > max_base_length:
            base_schema = base_schema[:max_base_length]
        return f"{base_schema}_{suffix}"
    
    # Production: return base schema unchanged
    return base_schema


def get_raw_dataset(
    config: Optional[Dict[str, Any]] = None,
    env: str = "dev"
) -> str:
    """
    Returns the raw dataset name with git-aware suffix in dev environment.
    
    Args:
        config: Optional configuration dict. If provided, checks for 'raw_dataset' override.
        env: Environment name ('dev' or 'prod'). Defaults to 'dev'.
        
    Returns:
        Raw dataset name string:
        - "msh_raw" by default (or "msh_raw_{suffix}" in dev)
        - Overridden by config['raw_dataset'] if present
        - In dev environment, suffix is appended based on git branch
    """
    # Get base raw dataset from config or use default
    if config and config.get("raw_dataset"):
        base_raw_dataset = config["raw_dataset"]
    else:
        base_raw_dataset = DEFAULT_RAW_DATASET
    
    # Apply git-aware suffix in dev environment
    if env == "dev":
        suffix = get_sanitized_schema_suffix()
        # Ensure total length doesn't exceed DB limits (63 chars for most DBs)
        # Leave room for suffix: base + "_" + suffix (max 20) = base + 21
        max_base_length = 63 - 21  # 42 chars for base dataset
        if len(base_raw_dataset) > max_base_length:
            base_raw_dataset = base_raw_dataset[:max_base_length]
        return f"{base_raw_dataset}_{suffix}"
    
    # Production: return base dataset unchanged
    return base_raw_dataset


def get_destination_credentials(destination: str, cwd: Optional[str] = None) -> Optional[str]:
    """
    Returns connection string for the specified destination.
    
    For DuckDB, returns default path if no credentials found in environment.
    For other destinations, returns None (expects environment variables).
    
    Args:
        destination: The destination type (e.g., 'duckdb', 'snowflake')
        cwd: Optional working directory for DuckDB default path resolution.
        
    Returns:
        Connection string, or None if not available.
    """
    if cwd is None:
        cwd = os.getcwd()
    
    if destination == "duckdb":
        # Default DuckDB path
        return f"duckdb:///{os.path.join(cwd, 'msh.duckdb')}"
    
    # For other destinations, credentials should come from environment variables
    # (handled by db_utils.get_connection_engine)
    return None


def resolve_env_vars(value: Any) -> Any:
    """
    Recursively resolves environment variables in configuration values.
    
    Replaces ${VAR_NAME} patterns with os.environ.get("VAR_NAME").
    Works with strings, dicts, and lists.
    
    Args:
        value: Configuration value (string, dict, list, or other)
        
    Returns:
        Value with environment variables resolved
    """
    if isinstance(value, str):
        # Pattern: ${VAR_NAME} or ${VAR_NAME}
        pattern = r'\$\{([^}]+)\}'
        
        def replace_env(match):
            var_name = match.group(1)
            env_value = os.environ.get(var_name)
            if env_value is None:
                console.warning(f"Environment variable '{var_name}' not found, leaving as-is")
                return match.group(0)  # Return original if not found
            return env_value
        
        return re.sub(pattern, replace_env, value)
    elif isinstance(value, dict):
        return {k: resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_env_vars(item) for item in value]
    else:
        return value


def resolve_source(
    source_name: str,
    table_name: Optional[str] = None,
    resource_name: Optional[str] = None,
    msh_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Resolves a source reference from msh.yaml into a full ingest config.
    
    Supports dbt-style source definitions where sources define credentials
    and available tables/resources. Individual .msh files reference sources
    by name and table/resource name.
    
    Args:
        source_name: Name of the source to resolve
        table_name: Optional table name (for SQL sources)
        resource_name: Optional resource name (for API sources)
        msh_config: Configuration dictionary from msh.yaml
        
    Returns:
        Fully resolved ingest config dictionary
        
    Raises:
        ValueError: If source or table/resource not found, or ambiguous config
    """
    if not msh_config:
        raise ValueError("msh_config is required for source resolution")
    
    sources = msh_config.get("sources", [])
    if not sources:
        raise ValueError(f"Source '{source_name}' not found: no sources defined in msh.yaml")
    
    # Find the source definition
    source_def = None
    for src in sources:
        if isinstance(src, dict) and src.get("name") == source_name:
            source_def = src
            break
    
    if not source_def:
        available = [s.get("name") for s in sources if isinstance(s, dict)]
        raise ValueError(
            f"Source '{source_name}' not found in msh.yaml. "
            f"Available sources: {', '.join(available) if available else 'none'}"
        )
    
    # Resolve environment variables in source config
    source_def = resolve_env_vars(source_def.copy())
    
    # Determine source type
    source_type = source_def.get("type")
    if not source_type:
        raise ValueError(f"Source '{source_name}' missing required field 'type'")
    
    # Build base ingest config from source
    ingest_config = {
        "type": source_type
    }
    
    # Copy source-level config
    if source_type == "sql_database":
        if "credentials" in source_def:
            ingest_config["credentials"] = source_def["credentials"]
        if "schema" in source_def:
            ingest_config["schema"] = source_def["schema"]
    elif source_type == "rest_api":
        if "endpoint" in source_def:
            ingest_config["endpoint"] = source_def["endpoint"]
        if "config" in source_def:
            ingest_config["config"] = source_def["config"]
    
    # Handle table/resource resolution
    if source_type == "sql_database":
        if not table_name:
            raise ValueError(f"Table name required for SQL database source '{source_name}'")
        
        # Handle schema.table format
        schema = None
        table = table_name
        if "." in table_name:
            parts = table_name.rsplit(".", 1)
            schema = parts[0]
            table = parts[1]
        
        # Find table definition
        tables = source_def.get("tables", [])
        table_def = None
        for tbl in tables:
            if isinstance(tbl, dict):
                if tbl.get("name") == table:
                    table_def = tbl
                    break
            elif isinstance(tbl, str) and tbl == table:
                table_def = {}
        
        if table_def is None:
            available = [
                t.get("name") if isinstance(t, dict) else t 
                for t in tables
            ]
            raise ValueError(
                f"Table '{table}' not found in source '{source_name}'. "
                f"Available tables: {', '.join(available) if available else 'none'}"
            )
        
        # Use schema from table definition or source default, or parsed schema
        if schema:
            ingest_config["schema"] = schema
        elif isinstance(table_def, dict) and "schema" in table_def:
            ingest_config["schema"] = table_def["schema"]
        elif "schema" in source_def:
            ingest_config["schema"] = source_def["schema"]
        
        # Build full table name
        final_schema = ingest_config.get("schema", "public")
        ingest_config["table"] = f"{final_schema}.{table}" if final_schema else table
        
        # Merge table-level config
        if isinstance(table_def, dict):
            for key in ["description", "columns", "meta"]:
                if key in table_def:
                    ingest_config[key] = table_def[key]
    
    elif source_type == "rest_api":
        if not resource_name:
            raise ValueError(f"Resource name required for REST API source '{source_name}'")
        
        # Find resource definition
        resources = source_def.get("resources", [])
        resource_def = None
        for res in resources:
            if isinstance(res, dict):
                if res.get("name") == resource_name:
                    resource_def = res
                    break
            elif isinstance(res, str) and res == resource_name:
                resource_def = {}
        
        if resource_def is None:
            available = [
                r.get("name") if isinstance(r, dict) else r 
                for r in resources
            ]
            raise ValueError(
                f"Resource '{resource_name}' not found in source '{source_name}'. "
                f"Available resources: {', '.join(available) if available else 'none'}"
            )
        
        ingest_config["resource"] = resource_name
        
        # Merge resource-level config (e.g., path override)
        if isinstance(resource_def, dict):
            if "path" in resource_def:
                # Override endpoint path if specified
                base_endpoint = ingest_config.get("endpoint", "")
                resource_path = resource_def["path"]
                if resource_path.startswith("/"):
                    ingest_config["endpoint"] = base_endpoint.rstrip("/") + resource_path
                else:
                    ingest_config["endpoint"] = base_endpoint.rstrip("/") + "/" + resource_path
            for key in ["description", "config"]:
                if key in resource_def:
                    if key == "config" and "config" in ingest_config:
                        # Merge configs
                        ingest_config["config"] = {**ingest_config["config"], **resource_def["config"]}
                    else:
                        ingest_config[key] = resource_def[key]
    
    return ingest_config


def expand_test_suites(
    test_suites: List[str],
    msh_config: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Expands test suite references into individual test assertions.
    
    Takes a list of test suite names and returns all tests from those suites.
    Supports merging multiple suites and individual tests.
    
    Args:
        test_suites: List of test suite names to expand
        msh_config: Configuration dictionary from msh.yaml
        
    Returns:
        List of test assertion dictionaries
        
    Raises:
        ValueError: If test suite not found
    """
    if not msh_config:
        raise ValueError("msh_config is required for test suite expansion")
    
    if not test_suites:
        return []
    
    config_test_suites = msh_config.get("test_suites", {})
    if not config_test_suites:
        available = []
        raise ValueError(
            f"Test suites requested but no test_suites defined in msh.yaml. "
            f"Requested suites: {', '.join(test_suites)}"
        )
    
    expanded_tests = []
    seen_tests = set()  # Track to avoid duplicates
    
    for suite_name in test_suites:
        if suite_name not in config_test_suites:
            available = list(config_test_suites.keys())
            raise ValueError(
                f"Test suite '{suite_name}' not found in msh.yaml. "
                f"Available suites: {', '.join(available) if available else 'none'}"
            )
        
        suite_tests = config_test_suites[suite_name]
        if not isinstance(suite_tests, list):
            raise ValueError(
                f"Test suite '{suite_name}' must be a list of test assertions"
            )
        
        for test in suite_tests:
            # Create a unique key for deduplication (simple string representation)
            test_key = str(test)
            if test_key not in seen_tests:
                expanded_tests.append(test)
                seen_tests.add(test_key)
    
    return expanded_tests


def apply_defaults(
    asset_data: Dict[str, Any],
    msh_config: Optional[Dict[str, Any]] = None,
    file_path: Optional[Union[str, Path]] = None
) -> Dict[str, Any]:
    """
    Applies layer-based config defaults to asset data.
    
    Merges defaults from msh.yaml based on the layer specified in the asset.
    Asset values override defaults. Supports deep merging of nested structures.
    
    Args:
        asset_data: Parsed asset data dictionary
        msh_config: Configuration dictionary from msh.yaml
        file_path: Optional file path for layer inference and error messages
        
    Returns:
        Asset data with defaults applied
        
    Raises:
        ValueError: If layer not found in defaults
    """
    if not msh_config:
        return asset_data
    
    defaults = msh_config.get("defaults", {})
    if not defaults:
        return asset_data
    
    # Determine layer
    layer = asset_data.get("layer")
    
    # If layer not specified, try to infer from file path
    if not layer and file_path:
        file_path_str = str(file_path)
        if "/staging/" in file_path_str or "\\staging\\" in file_path_str:
            layer = "staging"
        elif "/marts/" in file_path_str or "\\marts\\" in file_path_str:
            layer = "marts"
        elif "/intermediate/" in file_path_str or "\\intermediate\\" in file_path_str:
            layer = "intermediate"
    
    # If still no layer, return asset as-is
    if not layer:
        return asset_data
    
    # Check if layer exists in defaults
    if layer not in defaults:
        available = list(defaults.keys())
        file_context = f" in {file_path}" if file_path else ""
        raise ValueError(
            f"Layer '{layer}' not found in defaults{file_context}. "
            f"Available layers: {', '.join(available) if available else 'none'}"
        )
    
    layer_defaults = defaults[layer]
    if not isinstance(layer_defaults, dict):
        raise ValueError(f"Defaults for layer '{layer}' must be a dictionary")
    
    # Deep merge: defaults first, then asset data (asset overrides)
    merged = _deep_merge(layer_defaults.copy(), asset_data.copy())
    
    return merged


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merges two dictionaries, with override values taking precedence.
    
    Args:
        base: Base dictionary (defaults)
        override: Override dictionary (asset data)
        
    Returns:
        Merged dictionary
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dicts
            result[key] = _deep_merge(result[key], value)
        else:
            # Override takes precedence
            result[key] = value
    
    return result

