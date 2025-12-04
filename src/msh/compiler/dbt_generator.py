"""
dbt artifact generator module for msh compiler.

Generates dbt_project.yml, profiles.yml, and generic_loader.py.
"""
import yaml
import os
from typing import Dict, Any

from msh.constants import (
    DEFAULT_PROJECT_NAME, DEFAULT_PROFILE_NAME, DEFAULT_TARGET_NAME,
    DEFAULT_DUCKDB_PATH
)
from msh.utils.config import get_target_schema
from msh.logger import logger as console


class DbtArtifactGenerator:
    """Generates dbt project artifacts."""
    
    def __init__(self, build_dir: str, models_dir: str, msh_config: Dict[str, Any], env: str = "dev") -> None:
        """
        Initialize the generator.
        
        Args:
            build_dir: Directory where dbt artifacts will be written
            models_dir: Directory for dbt models
            msh_config: Configuration dictionary from msh.yaml
            env: Environment name ('dev' or 'prod'). Defaults to 'dev'.
        """
        self.build_dir = build_dir
        self.models_dir = models_dir
        self.msh_config = msh_config
        self.env = env
        self.destination = self.msh_config.get("destination", "duckdb")
    
    def generate_all(self) -> None:
        """Generate all dbt artifacts."""
        self.generate_project_yml()
        self.generate_profiles_yml()
        self.generate_generic_loader()
    
    def generate_project_yml(self) -> None:
        """Generates dbt_project.yml"""
        if not os.path.exists(self.build_dir):
            os.makedirs(self.build_dir)
        if not os.path.exists(self.models_dir):
            os.makedirs(self.models_dir)
            
        # dbt_project.yml
        dbt_project_content = {
            "name": DEFAULT_PROJECT_NAME,
            "version": "1.0.0",
            "config-version": 2,
            "profile": DEFAULT_PROFILE_NAME,
            "model-paths": ["models"],
            "clean-targets": ["target", "dbt_packages"],
            "models": {
                DEFAULT_PROJECT_NAME: {
                    "materialized": "table"
                }
            }
        }
        with open(os.path.join(self.build_dir, "dbt_project.yml"), "w") as f:
            yaml.dump(dbt_project_content, f)
    
    def generate_profiles_yml(self) -> None:
        """Generates profiles.yml"""
        outputs = {}
        
        # Get target schema from config (with git-aware suffix in dev)
        target_schema = get_target_schema(self.destination, self.msh_config, self.env)
        
        if self.destination == "duckdb":
            outputs[DEFAULT_TARGET_NAME] = {
                "type": "duckdb",
                "path": os.path.join(os.getcwd(), DEFAULT_DUCKDB_PATH)
            }
        elif self.destination == "postgres":
            # Expect env vars or config
            # We use dbt's env_var macro or just inject if we have them in msh_config
            # Ideally we rely on dbt env vars: DBT_HOST, DBT_USER, etc.
            # Or we map from DESTINATION__POSTGRES__CREDENTIALS?
            # dlt connection string: postgresql://user:pass@host:port/db
            # dbt needs separate fields.
            # For now, let's assume standard dbt env vars or a simple mapping if provided.
            
            # Simplified: Use env_var for flexibility
            outputs[DEFAULT_TARGET_NAME] = {
                "type": "postgres",
                "host": "{{ env_var('POSTGRES_HOST', 'localhost') }}",
                "user": "{{ env_var('POSTGRES_USER', 'postgres') }}",
                "pass": "{{ env_var('POSTGRES_PASSWORD', 'password') }}",
                "port": "{{ env_var('POSTGRES_PORT', 55432) | int }}",
                "dbname": "{{ env_var('POSTGRES_DB', 'postgres') }}",
                "schema": target_schema
            }
        elif self.destination == "snowflake":
            # Snowflake-specific profile generation with validation
            # Note: Other destinations (Postgres, DuckDB, BigQuery, etc.) continue to work normally
            # Validate required Snowflake environment variables
            required_vars = [
                "SNOWFLAKE_ACCOUNT",
                "SNOWFLAKE_USER",
                "SNOWFLAKE_PASSWORD",
                "SNOWFLAKE_DATABASE",
                "SNOWFLAKE_WAREHOUSE",
            ]
            missing_vars = [var for var in required_vars if not os.environ.get(var)]
            
            if missing_vars:
                raise ValueError(
                    f"Missing required Snowflake environment variables: {', '.join(missing_vars)}\n"
                    f"Please set these variables before running msh with Snowflake destination.\n"
                    f"Example:\n"
                    f"  export SNOWFLAKE_ACCOUNT=xyz123\n"
                    f"  export SNOWFLAKE_USER=msh_user\n"
                    f"  export SNOWFLAKE_PASSWORD=secure_password\n"
                    f"  export SNOWFLAKE_DATABASE=ANALYTICS\n"
                    f"  export SNOWFLAKE_WAREHOUSE=COMPUTE_WH"
                )
            
            # Validate schema name for Snowflake
            if len(target_schema) > 255:
                console.warning(
                    f"Schema name '{target_schema}' exceeds Snowflake max length (255). "
                    f"Consider using a shorter name."
                )
            
            outputs[DEFAULT_TARGET_NAME] = {
                "type": "snowflake",
                "account": "{{ env_var('SNOWFLAKE_ACCOUNT') }}",
                "user": "{{ env_var('SNOWFLAKE_USER') }}",
                "password": "{{ env_var('SNOWFLAKE_PASSWORD') }}",
                "role": "{{ env_var('SNOWFLAKE_ROLE', '') }}",
                "database": "{{ env_var('SNOWFLAKE_DATABASE') }}",
                "warehouse": "{{ env_var('SNOWFLAKE_WAREHOUSE') }}",
                "schema": target_schema
            }
        else:
            # Fallback or error?
            # Let's default to duckdb if unknown, or warn.
            console.warning(f"Unknown destination '{self.destination}'. Defaulting profile to DuckDB.")
            outputs[DEFAULT_TARGET_NAME] = {
                "type": "duckdb",
                "path": os.path.join(os.getcwd(), DEFAULT_DUCKDB_PATH)
            }

        profiles_content = {
            DEFAULT_PROFILE_NAME: {
                "target": DEFAULT_TARGET_NAME,
                "outputs": outputs
            }
        }
        with open(os.path.join(self.build_dir, "profiles.yml"), "w") as f:
            yaml.dump(profiles_content, f)
    
    def generate_generic_loader(self) -> None:
        """Generates generic_loader.py model file."""
        # generic_loader.py
        # We need to call generic_loader from msh_engine.generic
        generic_loader_code = """
import msh_engine.generic

def model(dbt, session):
    dbt.config(
        materialized='table'
    )
    return msh_engine.generic.generic_loader(dbt)
"""
        with open(os.path.join(self.models_dir, "generic_loader.py"), "w") as f:
            f.write(generic_loader_code)

