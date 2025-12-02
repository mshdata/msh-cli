"""
dbt artifacts writer module for msh compiler.

Generates sources.yml, schema.yml, and exposures.yml for dbt lineage and tests.
"""
import yaml
import os
from typing import List, Dict, Any


class DbtArtifactWriter:
    """Writes dbt artifact YAML files."""
    
    def __init__(self, models_dir: str, raw_dataset: str) -> None:
        """
        Initialize the writer.
        
        Args:
            models_dir: Directory where dbt models are located
            raw_dataset: Name of the raw dataset (for sources.yml)
        """
        self.models_dir = models_dir
        self.raw_dataset = raw_dataset
    
    def write_sources(self, execution_plan: List[Dict[str, Any]]) -> None:
        """
        Generates models/sources.yml for full lineage.
        
        Args:
            execution_plan: List of asset metadata dictionaries
        """
        tables = []
        for item in execution_plan:
            tables.append({
                "name": item["raw_table"],
                "description": f"Ingested via msh (Asset: {item['name']})"
            })
            
        sources_content = {
            "version": 2,
            "sources": [
                {
                    "name": self.raw_dataset,
                    "tables": tables
                }
            ]
        }
        
        sources_path = os.path.join(self.models_dir, "sources.yml")
        with open(sources_path, "w") as f:
            yaml.dump(sources_content, f)
    
    def write_schema(self, execution_plan: List[Dict[str, Any]]) -> None:
        """
        Generates models/schema.yml for Atomic Quality (dbt tests).
        Supports both 'quality' (legacy) and 'tests' (new) blocks.
        
        Args:
            execution_plan: List of asset metadata dictionaries
        """
        models = []
        for item in execution_plan:
            tests_block = item.get("tests")
            quality_block = item.get("quality")
            
            columns_config = {}
            
            # Handle new 'tests' block
            # tests:
            #   - unique: id
            #   - not_null: email
            if tests_block:
                for test in tests_block:
                    if isinstance(test, dict):
                        for test_type, column in test.items():
                            if column not in columns_config:
                                columns_config[column] = []
                            columns_config[column].append(test_type)

            # Handle legacy 'quality' block (merging if both exist)
            if quality_block:
                for rule in quality_block:
                    if isinstance(rule, dict):
                        for test_type, targets in rule.items():
                            if test_type == "accepted_values":
                                col = targets.get("column")
                                vals = targets.get("values")
                                if col:
                                    if col not in columns_config:
                                        columns_config[col] = []
                                    columns_config[col].append({
                                        "accepted_values": {"values": vals}
                                    })
                            elif isinstance(targets, list):
                                for col in targets:
                                    if col not in columns_config:
                                        columns_config[col] = []
                                    columns_config[col].append(test_type)
                            elif isinstance(targets, str):
                                col = targets
                                if col not in columns_config:
                                    columns_config[col] = []
                                columns_config[col].append(test_type)
                                
            if columns_config:
                # Construct model entry
                model_columns = []
                for col_name, tests in columns_config.items():
                    model_columns.append({
                        "name": col_name,
                        "tests": tests
                    })
                    
                models.append({
                    "name": item["model_name"], # We test the Blue/Green model before swap
                    "columns": model_columns
                })
                
        if not models:
            return
            
        schema_content = {
            "version": 2,
            "models": models
        }
        
        schema_path = os.path.join(self.models_dir, "schema.yml")
        with open(schema_path, "w") as f:
            yaml.dump(schema_content, f)
    
    def write_exposures(self, execution_plan: List[Dict[str, Any]]) -> None:
        """
        Generates models/exposures.yml for Lineage (BI Dashboards).
        
        Args:
            execution_plan: List of asset metadata dictionaries
        """
        exposures = []
        for item in execution_plan:
            expose = item.get("expose")
            if expose:
                # expose:
                #   - name: revenue_dashboard
                #     type: dashboard
                #     url: ...
                #     owner: ...
                
                for exp in expose:
                    # We automatically link to the current asset
                    depends_on = exp.get("depends_on", [])
                    # Add current model ref if not present
                    # We use the model_name (Green) or just the asset name?
                    # dbt exposures depend on nodes. ref('asset_name') works if asset_name is a model.
                    # Our models are named model_{name}_{hash}.
                    # But we swap them to view {name}.
                    # dbt lineage usually tracks models.
                    # If we ref('model_name'), it links to the specific version.
                    # If we ref('name'), it links to the view? But dbt doesn't know about the view unless we define it as a source or model.
                    # Actually, our dbt project only knows about model_{name}_{hash}.
                    # So we should link to that.
                    
                    # But wait, if we link to model_{name}_{hash}, the exposure will point to a specific version.
                    # That's fine for the graph.
                    
                    current_ref = f"ref('{item['model_name']}')"
                    # But dbt exposures syntax for depends_on is list of refs.
                    # We can just add the model name to the list if we are generating the YAML.
                    # In YAML: depends_on: - ref('model_foo')
                    # Actually, dbt expects: depends_on: - ref('model') or - source('src', 'table')
                    
                    # Let's construct the list.
                    deps = []
                    deps.append(f"ref('{item['model_name']}')")
                    
                    exposures.append({
                        "name": exp.get("name"),
                        "type": exp.get("type", "dashboard"),
                        "url": exp.get("url"),
                        "owner": {
                            "name": exp.get("owner"),
                            "email": exp.get("email") # Optional
                        },
                        "depends_on": deps
                    })

        if not exposures:
            return

        exposures_content = {
            "version": 2,
            "exposures": exposures
        }

        exposures_path = os.path.join(self.models_dir, "exposures.yml")
        with open(exposures_path, "w") as f:
            yaml.dump(exposures_content, f)

