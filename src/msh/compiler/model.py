"""
Model compiler module for msh compiler.

Compiles individual asset models into dbt SQL files.
"""
import os
import jinja2
from typing import Dict, Any, Optional
from msh.logger import logger as console


class ModelCompiler:
    """Compiles asset models into dbt SQL files."""
    
    def __init__(
        self, 
        models_dir: str, 
        raw_dataset: str,
        msh_config: Optional[Dict[str, Any]] = None,
        project_root: Optional[str] = None
    ) -> None:
        """
        Initialize the compiler.
        
        Args:
            models_dir: Directory where dbt models will be written
            raw_dataset: Name of the raw dataset (for source references)
            msh_config: Optional configuration dictionary for variable resolution
            project_root: Optional project root directory for macro loading
        """
        self.models_dir = models_dir
        self.raw_dataset = raw_dataset
        self.msh_config = msh_config or {}
        
        # Create Jinja2 environment with var() function
        self.jinja_env = jinja2.Environment(
            loader=jinja2.BaseLoader(),
            undefined=jinja2.StrictUndefined
        )
        
        # Add var() function to Jinja2 environment
        def var_function(var_name: str) -> str:
            """Jinja2 function to look up variables from msh.yaml."""
            vars_dict = self.msh_config.get("vars", {})
            if var_name not in vars_dict:
                available = list(vars_dict.keys())
                raise ValueError(
                    f"Variable '{var_name}' not found in msh.yaml vars. "
                    f"Available variables: {', '.join(available) if available else 'none'}"
                )
            return str(vars_dict[var_name])
        
        self.jinja_env.globals['var'] = var_function
        
        # Load macros from macros/ directory if project_root is provided
        self.macros = {}
        if project_root:
            from msh.compiler.macros import load_macros
            try:
                self.macros = load_macros(project_root, self.jinja_env)
                # Add macros to Jinja2 environment globals
                for macro_name, macro_func in self.macros.items():
                    self.jinja_env.globals[macro_name] = macro_func
            except Exception as e:
                console.warning(f"Failed to load macros: {e}")
    
    def compile(
        self, 
        asset: Dict[str, Any], 
        content_hash: str,
        extract_columns_fn
    ) -> Dict[str, Any]:
        """
        Generates the SQL model for Blue/Green deployment.
        Target Model Name: model_{asset_name}_{hash}
        Source Table Name: raw_{asset_name}_{hash}
        
        Args:
            asset: Asset data dictionary
            content_hash: Content hash for versioning
            extract_columns_fn: Function to extract columns from SQL (for Smart Ingest)
            
        Returns:
            Dictionary containing compiled model metadata
        """
        name = asset.get("name")
        transform_sql = asset.get("transform")
        python_code = asset.get("python") # Phase 8: Python Transformation
        
        # Blue/Green Names
        raw_table_name = f"raw_{name}_{content_hash}"
        model_name = f"model_{name}_{content_hash}"
        
        # Replace {{ source }} with a placeholder before Jinja2 rendering
        # This prevents Jinja2 from trying to process it as a variable
        source_placeholder = "__MSH_SOURCE_PLACEHOLDER__"
        sql_with_placeholder = transform_sql.replace("{{ source }}", source_placeholder)
        
        # Render Jinja2 template (for var() function and other Jinja features)
        try:
            template = self.jinja_env.from_string(sql_with_placeholder)
            rendered_sql = template.render()
        except jinja2.UndefinedError as e:
            raise ValueError(f"Undefined variable in SQL: {e}")
        except Exception as e:
            raise ValueError(f"Error rendering SQL template: {e}")
        
        # Replace placeholder with dbt source macro for lineage
        # We use the configured raw_dataset
        dbt_source_str = f"{{{{ source('{self.raw_dataset}', '{raw_table_name}') }}}}"
        compiled_sql = rendered_sql.replace(source_placeholder, dbt_source_str)
        
        # Inject config block for alias
        config_block = f"{{{{ config(alias='{model_name}', materialized='table') }}}}\n\n"
        final_sql = config_block + compiled_sql
        
        # Write to file (Use clean name so {{ ref('name') }} works)
        model_path = os.path.join(self.models_dir, f"{name}.sql")
        with open(model_path, "w") as f:
            f.write(final_sql)
            
        return {
            "name": name,
            "hash": content_hash,
            "raw_table": raw_table_name,
            "model_name": model_name,
            "raw_sql": transform_sql,  # Store raw SQL for dependency resolution
            "columns": extract_columns_fn(transform_sql) if extract_columns_fn else None,
            "python_code": python_code,
            "contract": asset.get("contract"),
            "primary_key": asset.get("primary_key"),
            "write_disposition": asset.get("write_disposition", "replace"),
            "freshness": asset.get("freshness"),
            "quality": asset.get("quality"),
            "tests": asset.get("tests"),
            "incremental": asset.get("incremental"),
            "expose": asset.get("expose")
        }

