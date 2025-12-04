"""
Manifest Generator for msh.

Generates project-level manifest.json for AI context.
"""
import os
import json
import glob
from pathlib import Path
from typing import Dict, Any, List, Optional
from msh.ai.metadata import MetadataExtractor
from msh.ai.metadata_cache import MetadataCache
from msh.utils.config import load_msh_config
from msh.logger import logger


class ManifestGenerator:
    """Generates project-level manifest for AI context."""
    
    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize manifest generator.
        
        Args:
            project_root: Project root directory. Defaults to current working directory.
        """
        if project_root is None:
            project_root = os.getcwd()
        
        self.project_root = project_root
        self.msh_config = load_msh_config(project_root)
        self.extractor = MetadataExtractor(msh_config=self.msh_config)
        self.cache = MetadataCache(project_root=project_root)
    
    def generate_manifest(self, update: bool = False) -> Dict[str, Any]:
        """
        Generate project-level manifest.
        
        Args:
            update: If True, update existing manifest. If False, generate from scratch.
            
        Returns:
            Manifest dictionary
        """
        # Load existing manifest if update mode
        existing_manifest = None
        if update:
            existing_manifest = self.cache.load_manifest()
        
        # Find all .msh files
        msh_files = self._find_msh_files()
        
        # Generate manifest
        manifest = {
            "project": {
                "id": os.path.basename(self.project_root),
                "name": os.path.basename(self.project_root),
                "warehouse": self.msh_config.get("destination", "unknown"),
                "default_schema": self.msh_config.get("target_schema", "main"),
                "raw_dataset": self.msh_config.get("raw_dataset", "msh_raw"),
            },
            "assets": [],
            "generated_at": self._get_timestamp(),
        }
        
        # Extract metadata for each asset
        for msh_file in msh_files:
            try:
                asset_metadata = self.extractor.extract_asset_metadata(
                    msh_file,
                    self.project_root
                )
                manifest["assets"].append(asset_metadata)
            except Exception as e:
                logger.warning(f"Failed to extract metadata from {msh_file}: {e}")
                continue
        
        # Save to cache
        self.cache.save_manifest(manifest)
        
        return manifest
    
    def generate_lineage(self) -> Dict[str, Any]:
        """
        Generate lineage graph from assets.
        
        Returns:
            Lineage dictionary with edges
        """
        manifest = self.cache.load_manifest()
        if not manifest:
            manifest = self.generate_manifest()
        
        edges = []
        asset_map = {asset["id"]: asset for asset in manifest.get("assets", [])}
        
        # Build edges from dependencies
        for asset in manifest.get("assets", []):
            asset_id = asset["id"]
            lineage = asset.get("lineage", {})
            upstream = lineage.get("upstream", [])
            
            for upstream_id in upstream:
                if upstream_id in asset_map:
                    edges.append({
                        "from": upstream_id,
                        "to": asset_id,
                        "relationship": "depends_on"
                    })
        
        lineage_graph = {
            "edges": edges,
            "generated_at": self._get_timestamp(),
        }
        
        # Save to cache
        self.cache.save_lineage(lineage_graph)
        
        return lineage_graph
    
    def generate_schemas(self) -> Dict[str, Any]:
        """
        Generate flattened schema view.
        
        Returns:
            Schemas dictionary indexed by asset ID
        """
        manifest = self.cache.load_manifest()
        if not manifest:
            manifest = self.generate_manifest()
        
        schemas = {}
        
        for asset in manifest.get("assets", []):
            asset_id = asset["id"]
            schema = asset.get("schema", {})
            schemas[asset_id] = schema
        
        schemas_index = {
            "schemas": schemas,
            "generated_at": self._get_timestamp(),
        }
        
        # Save to cache
        self.cache.save_schemas(schemas_index)
        
        return schemas_index
    
    def generate_tests_index(self) -> Dict[str, Any]:
        """
        Generate test definitions and statuses index.
        
        Returns:
            Tests index dictionary
        """
        manifest = self.cache.load_manifest()
        if not manifest:
            manifest = self.generate_manifest()
        
        tests_index = {}
        
        for asset in manifest.get("assets", []):
            asset_id = asset["id"]
            tests = asset.get("tests", [])
            tests_index[asset_id] = {
                "tests": tests,
                "count": len(tests),
            }
        
        tests_data = {
            "tests": tests_index,
            "generated_at": self._get_timestamp(),
        }
        
        # Save to cache
        self.cache.save_tests(tests_data)
        
        return tests_data
    
    def generate_all(self) -> None:
        """Generate all metadata cache files."""
        logger.info("Generating metadata cache...")
        
        # Generate manifest first (required for others)
        self.generate_manifest()
        
        # Generate lineage
        self.generate_lineage()
        
        # Generate schemas
        self.generate_schemas()
        
        # Generate tests
        self.generate_tests_index()
        
        logger.info("Metadata cache generation complete")
    
    def _find_msh_files(self) -> List[str]:
        """Find all .msh files in project."""
        msh_files = []
        
        # Search in project root and subdirectories
        for root, dirs, files in os.walk(self.project_root):
            # Skip hidden directories and .msh directory
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if file.endswith('.msh'):
                    msh_files.append(os.path.join(root, file))
        
        return sorted(msh_files)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()

