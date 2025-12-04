"""
Metadata Cache Management for msh.

Manages the .msh/ metadata cache directory structure for fast AI operations.
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from msh.logger import logger


class MetadataCache:
    """Manages metadata cache in .msh/ directory."""
    
    CACHE_DIR = ".msh"
    MANIFEST_FILE = "manifest.json"
    LINEAGE_FILE = "lineage.json"
    SCHEMAS_FILE = "schemas.json"
    TESTS_FILE = "tests.json"
    VERSIONS_FILE = "versions.json"
    
    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize metadata cache.
        
        Args:
            project_root: Project root directory. Defaults to current working directory.
        """
        if project_root is None:
            project_root = os.getcwd()
        
        self.project_root = project_root
        self.cache_dir = os.path.join(project_root, self.CACHE_DIR)
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def save_manifest(self, manifest: Dict[str, Any]) -> None:
        """Save manifest.json to cache."""
        file_path = os.path.join(self.cache_dir, self.MANIFEST_FILE)
        with open(file_path, "w") as f:
            json.dump(manifest, f, indent=2)
        logger.debug(f"Saved manifest to {file_path}")
    
    def load_manifest(self) -> Optional[Dict[str, Any]]:
        """Load manifest.json from cache."""
        file_path = os.path.join(self.cache_dir, self.MANIFEST_FILE)
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load manifest: {e}")
            return None
    
    def save_lineage(self, lineage: Dict[str, Any]) -> None:
        """Save lineage.json to cache."""
        file_path = os.path.join(self.cache_dir, self.LINEAGE_FILE)
        with open(file_path, "w") as f:
            json.dump(lineage, f, indent=2)
        logger.debug(f"Saved lineage to {file_path}")
    
    def load_lineage(self) -> Optional[Dict[str, Any]]:
        """Load lineage.json from cache."""
        file_path = os.path.join(self.cache_dir, self.LINEAGE_FILE)
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load lineage: {e}")
            return None
    
    def save_schemas(self, schemas: Dict[str, Any]) -> None:
        """Save schemas.json to cache."""
        file_path = os.path.join(self.cache_dir, self.SCHEMAS_FILE)
        with open(file_path, "w") as f:
            json.dump(schemas, f, indent=2)
        logger.debug(f"Saved schemas to {file_path}")
    
    def load_schemas(self) -> Optional[Dict[str, Any]]:
        """Load schemas.json from cache."""
        file_path = os.path.join(self.cache_dir, self.SCHEMAS_FILE)
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load schemas: {e}")
            return None
    
    def save_tests(self, tests: Dict[str, Any]) -> None:
        """Save tests.json to cache."""
        file_path = os.path.join(self.cache_dir, self.TESTS_FILE)
        with open(file_path, "w") as f:
            json.dump(tests, f, indent=2)
        logger.debug(f"Saved tests to {file_path}")
    
    def load_tests(self) -> Optional[Dict[str, Any]]:
        """Load tests.json from cache."""
        file_path = os.path.join(self.cache_dir, self.TESTS_FILE)
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load tests: {e}")
            return None
    
    def save_versions(self, versions: Dict[str, Any]) -> None:
        """Save versions.json to cache."""
        file_path = os.path.join(self.cache_dir, self.VERSIONS_FILE)
        with open(file_path, "w") as f:
            json.dump(versions, f, indent=2)
        logger.debug(f"Saved versions to {file_path}")
    
    def load_versions(self) -> Optional[Dict[str, Any]]:
        """Load versions.json from cache."""
        file_path = os.path.join(self.cache_dir, self.VERSIONS_FILE)
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load versions: {e}")
            return None
    
    def clear_cache(self) -> None:
        """Clear all cache files."""
        cache_files = [
            self.MANIFEST_FILE,
            self.LINEAGE_FILE,
            self.SCHEMAS_FILE,
            self.TESTS_FILE,
            self.VERSIONS_FILE,
        ]
        
        for cache_file in cache_files:
            file_path = os.path.join(self.cache_dir, cache_file)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Removed cache file: {file_path}")

