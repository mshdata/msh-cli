"""
Context Pack Generator for msh.

Generates AI-ready context packs for assets or projects.
"""
import os
from typing import Dict, Any, List, Optional
from msh.ai.metadata_cache import MetadataCache
from msh.ai.manifest import ManifestGenerator
from msh.logger import logger


class ContextPackGenerator:
    """Generates AI-ready context packs."""
    
    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize context pack generator.
        
        Args:
            project_root: Project root directory. Defaults to current working directory.
        """
        if project_root is None:
            project_root = os.getcwd()
        
        self.project_root = project_root
        self.cache = MetadataCache(project_root=project_root)
        self.manifest_gen = ManifestGenerator(project_root=project_root)
    
    def generate_context_pack(
        self,
        asset_id: Optional[str] = None,
        include_tests: bool = False,
        include_history: bool = False,
        user_request: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate AI-ready context pack.
        
        Args:
            asset_id: Optional asset ID to focus the context pack on
            include_tests: Include test metadata
            include_history: Include recent run/deploy history
            user_request: Natural language request the user made
            
        Returns:
            Context pack dictionary matching context_pack schema
        """
        # Ensure manifest exists
        manifest = self.cache.load_manifest()
        if not manifest:
            logger.info("Manifest not found, generating...")
            manifest = self.manifest_gen.generate_manifest()
        
        # Load lineage
        lineage = self.cache.load_lineage()
        if not lineage:
            logger.info("Lineage not found, generating...")
            lineage = self.manifest_gen.generate_lineage()
        
        # Load schemas
        schemas = self.cache.load_schemas()
        if not schemas:
            logger.info("Schemas not found, generating...")
            schemas = self.manifest_gen.generate_schemas()
        
        # Load tests if requested
        tests = None
        if include_tests:
            tests_data = self.cache.load_tests()
            if not tests_data:
                logger.info("Tests not found, generating...")
                tests_data = self.manifest_gen.generate_tests_index()
            tests = tests_data.get("tests", {})
        
        # Load glossary (will be implemented in Phase 3)
        glossary_terms = []
        glossary_file = os.path.join(self.project_root, ".msh", "glossary.json")
        if os.path.exists(glossary_file):
            try:
                import json
                with open(glossary_file, "r") as f:
                    glossary_data = json.load(f)
                    glossary_terms = glossary_data.get("terms", [])
            except Exception as e:
                logger.warning(f"Failed to load glossary: {e}")
        
        # Filter assets if asset_id specified
        assets = manifest.get("assets", [])
        if asset_id:
            # Find the specific asset
            target_asset = None
            for asset in assets:
                if asset.get("id") == asset_id:
                    target_asset = asset
                    break
            
            if target_asset:
                # Include upstream and downstream assets
                upstream_ids = set(target_asset.get("lineage", {}).get("upstream", []))
                downstream_ids = set()
                
                # Find downstream assets
                for edge in lineage.get("edges", []):
                    if edge.get("from") == asset_id:
                        downstream_ids.add(edge.get("to"))
                
                # Build focused asset list
                focused_assets = [target_asset]
                for asset in assets:
                    asset_id_check = asset.get("id")
                    if asset_id_check in upstream_ids or asset_id_check in downstream_ids:
                        focused_assets.append(asset)
                
                assets = focused_assets
            else:
                logger.warning(f"Asset '{asset_id}' not found in manifest")
                assets = []
        
        # Build context pack
        context_pack = {
            "project": manifest.get("project", {}),
            "assets": self._optimize_assets(assets),
            "lineage": lineage.get("edges", []),
        }
        
        if include_tests and tests:
            context_pack["tests"] = self._optimize_tests(tests, assets)
        
        if glossary_terms:
            context_pack["glossary_terms"] = glossary_terms
        
        if user_request:
            context_pack["user_request"] = user_request
        
        # Add metrics and policies (will be populated from glossary in Phase 3)
        context_pack["metrics"] = []
        context_pack["policies"] = []
        
        return context_pack
    
    def _optimize_assets(self, assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Optimize assets for LLM token limits.
        
        Truncates large schemas and SQL if needed.
        """
        optimized = []
        
        for asset in assets:
            optimized_asset = asset.copy()
            
            # Truncate SQL if too long
            transform_block = optimized_asset.get("blocks", {}).get("transform", {})
            sql = transform_block.get("sql", "")
            if len(sql) > 2000:
                optimized_asset["blocks"]["transform"]["sql"] = sql[:2000] + "\n... (truncated)"
            
            # Limit schema columns
            schema = optimized_asset.get("schema", {})
            columns = schema.get("columns", [])
            if len(columns) > 50:
                schema["columns"] = columns[:50]
                schema["_truncated"] = True
                schema["_total_columns"] = len(columns)
            
            optimized.append(optimized_asset)
        
        return optimized
    
    def _optimize_tests(
        self,
        tests: Dict[str, Any],
        assets: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Optimize test data for context pack."""
        asset_ids = {asset.get("id") for asset in assets}
        optimized_tests = []
        
        for asset_id, test_data in tests.items():
            if asset_id in asset_ids:
                optimized_tests.append({
                    "asset_id": asset_id,
                    "tests": test_data.get("tests", [])[:10],  # Limit to 10 tests
                    "count": test_data.get("count", 0),
                })
        
        return optimized_tests

