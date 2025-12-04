import os
import json
import datetime
from typing import List, Dict, Any, Optional
from rich.console import Console
from msh.logger import logger as console_logger
from msh.ai.manifest import ManifestGenerator

class CatalogGenerator:
    def __init__(self, cwd: str, build_dir: str, console: Optional[Console] = None) -> None:
        self.cwd: str = cwd
        self.build_dir: str = build_dir
        self.console: Console = console or Console()
    
    def _load_test_results(self, asset_name: str) -> Optional[Dict[str, Any]]:
        """
        Load test results for an asset from .msh/test_results.json.
        
        Args:
            asset_name: Asset name
            
        Returns:
            Test results dictionary or None if not found
        """
        test_results_file = os.path.join(self.cwd, ".msh", "test_results.json")
        if not os.path.exists(test_results_file):
            return None
        
        try:
            with open(test_results_file, "r") as f:
                all_results = json.load(f)
            return all_results.get(asset_name)
        except (json.JSONDecodeError, IOError, OSError):
            return None
    
    def _calculate_pass_rate(self, results: Dict[str, Any]) -> float:
        """
        Calculate pass rate from test results.
        
        Args:
            results: Test results dictionary
            
        Returns:
            Pass rate as float (0.0 to 1.0)
        """
        summary = results.get("summary", {})
        total = summary.get("total", 0)
        if total == 0:
            return 0.0
        passed = summary.get("passed", 0)
        return passed / total

    def generate(self, execution_plan: List[Dict[str, Any]]) -> None:
        try:
            catalog = {
                "meta": {
                    "generated_at": datetime.datetime.now().isoformat(),
                    "version": "0.1.0",
                    "project_name": os.path.basename(self.cwd)
                },
                "assets": []
            }
            
            run_meta_dir = os.path.join(self.cwd, ".msh", "run_meta")
            manifest_path = os.path.join(self.build_dir, "target", "manifest.json")
            manifest_nodes = {}
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, "r") as f:
                        manifest = json.load(f)
                        manifest_nodes = manifest.get("nodes", {})
                        manifest_nodes.update(manifest.get("sources", {}))
                except (json.JSONDecodeError, IOError, OSError) as e:
                    # Non-critical: catalog generation can continue without manifest
                    console_logger.debug(f"Failed to load manifest.json (catalog generation will continue): {e}")
                    pass

            for asset in execution_plan:
                name = asset["name"]
                raw_table = asset["raw_table"]
                
                dbt_node = None
                for key, node in manifest_nodes.items():
                    if node.get("name") == name and node.get("resource_type") == "model":
                        dbt_node = node
                        break
                
                upstreams = []
                if dbt_node:
                    depends_on = dbt_node.get("depends_on", {}).get("nodes", [])
                    for parent_id in depends_on:
                        parts = parent_id.split(".")
                        resource_type = parts[0]
                        node_name = parts[-1]
                        if resource_type == "source":
                            upstreams.append(f"source:{node_name}")
                        elif resource_type == "model":
                            if node_name.startswith("model_"):
                                upstreams.append(node_name)
                            else:
                                upstreams.append(node_name)
                
                ingest_stats = {"status": "no_metrics_found"}
                meta_file = os.path.join(run_meta_dir, f"{raw_table}.json")
                if os.path.exists(meta_file):
                    try:
                        with open(meta_file, "r") as f:
                            ingest_stats = json.load(f)
                    except (json.JSONDecodeError, IOError, OSError) as e:
                        # Non-critical: continue with default stats
                        console_logger.debug(f"Failed to load metadata for {raw_table} (using defaults): {e}")
                        pass
                
                description = ""
                sql_data = {"raw": "", "compiled": ""}
                columns_data = []
                test_count = 0
                
                if dbt_node:
                    description = dbt_node.get("description", "")
                    sql_data["raw"] = dbt_node.get("raw_code", "")
                    sql_data["compiled"] = dbt_node.get("compiled_code", "")
                    dbt_columns = dbt_node.get("columns", {})
                    for col_name, col_def in dbt_columns.items():
                        columns_data.append({
                            "name": col_name,
                            "type": col_def.get("data_type", "UNKNOWN"),
                            "description": col_def.get("description", "")
                        })
                    node_id = dbt_node.get("unique_id")
                    if node_id:
                        for t_key, t_node in manifest_nodes.items():
                            if t_node.get("resource_type") == "test":
                                depends_on = t_node.get("depends_on", {}).get("nodes", [])
                                if node_id in depends_on:
                                    test_count += 1

                # Load test results if available
                latest_test_results = self._load_test_results(name)
                test_info = {"count": test_count}
                if latest_test_results:
                    test_info.update({
                        "results": latest_test_results.get("tests", []),
                        "last_run": latest_test_results.get("timestamp"),
                        "pass_rate": self._calculate_pass_rate(latest_test_results)
                    })
                
                asset_entry = {
                    "name": name,
                    "status": "healthy",
                    "hash": asset["hash"],
                    "description": description,
                    "sql": sql_data,
                    "columns": columns_data,
                    "tests": test_info,
                    "ingest": ingest_stats,
                    "upstreams": upstreams,
                    "transform": {
                        "materialization": asset.get("materialization", "view"),
                        "raw_sql": asset.get("raw_sql"),
                        "compiled_sql": asset.get("compiled_sql")
                    },
                    "file_path": asset.get("file_path")
                }
                catalog["assets"].append(asset_entry)
                
            catalog_path = os.path.join(self.cwd, ".msh", "msh_catalog.json")
            with open(catalog_path, "w") as f:
                json.dump(catalog, f, indent=2)
            
            # Also generate metadata cache for AI operations
            try:
                manifest_gen = ManifestGenerator(project_root=self.cwd)
                manifest_gen.generate_all()
            except Exception as e:
                # Non-critical: catalog generation succeeded, cache generation failed
                console_logger.warning(f"Failed to generate metadata cache: {e}")
                
        except Exception as e:
            self.console.print(f"[bold red]Error generating catalog: {e}[/bold red]")
