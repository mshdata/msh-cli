"""
Glossary model and operations for msh.

Supports dual glossary storage (project YAML + .msh/glossary.json cache).
"""
import os
import json
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
from msh.logger import logger


class Glossary:
    """Manages glossary operations."""
    
    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize glossary.
        
        Args:
            project_root: Project root directory. Defaults to current working directory.
        """
        if project_root is None:
            project_root = os.getcwd()
        
        self.project_root = project_root
        self.glossary_yaml_path = os.path.join(project_root, "glossary.yaml")
        self.glossary_json = os.path.join(project_root, ".msh", "glossary.json")
        
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        os.makedirs(os.path.dirname(self.glossary_json), exist_ok=True)
    
    def load(self) -> Dict[str, Any]:
        """
        Load glossary from YAML or JSON cache.
        
        Returns:
            Glossary dictionary
        """
        # Try to load from JSON cache first
        if os.path.exists(self.glossary_json):
            try:
                with open(self.glossary_json, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load glossary cache: {e}")
        
        # Try to load from YAML
        if os.path.exists(self.glossary_yaml_path):
            try:
                with open(self.glossary_yaml_path, "r") as f:
                    glossary_data = yaml.safe_load(f) or {}
                    # Save to cache
                    self.save_cache(glossary_data)
                    return glossary_data
            except (yaml.YAMLError, IOError) as e:
                logger.warning(f"Failed to load glossary YAML: {e}")
        
        # Try msh.yaml glossary section
        msh_yaml_path = os.path.join(self.project_root, "msh.yaml")
        if os.path.exists(msh_yaml_path):
            try:
                with open(msh_yaml_path, "r") as f:
                    msh_config = yaml.safe_load(f) or {}
                    if "glossary" in msh_config:
                        glossary_data = msh_config["glossary"]
                        # Ensure it has project field
                        if "project" not in glossary_data:
                            glossary_data["project"] = os.path.basename(self.project_root)
                        self.save_cache(glossary_data)
                        return glossary_data
            except (yaml.YAMLError, IOError) as e:
                logger.warning(f"Failed to load glossary from msh.yaml: {e}")
        
        # Return empty glossary
        return {
            "project": os.path.basename(self.project_root),
            "terms": [],
            "metrics": [],
            "dimensions": [],
            "policies": [],
        }
    
    def save(self, glossary_data: Dict[str, Any]) -> None:
        """
        Save glossary to YAML and JSON cache.
        
        Args:
            glossary_data: Glossary dictionary
        """
        # Save to YAML
        try:
            with open(self.glossary_yaml_path, "w") as f:
                yaml.dump(glossary_data, f, default_flow_style=False, sort_keys=False)
        except IOError as e:
            logger.warning(f"Failed to save glossary YAML: {e}")
        
        # Save to cache
        self.save_cache(glossary_data)
    
    def save_cache(self, glossary_data: Dict[str, Any]) -> None:
        """
        Save glossary to JSON cache.
        
        Args:
            glossary_data: Glossary dictionary
        """
        try:
            os.makedirs(os.path.dirname(self.glossary_json), exist_ok=True)
            with open(self.glossary_json, "w") as f:
                json.dump(glossary_data, f, indent=2)
        except IOError as e:
            logger.warning(f"Failed to save glossary cache: {e}")
    
    def add_term(
        self,
        name: str,
        description: Optional[str] = None,
        term_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a new glossary term.
        
        Args:
            name: Term name
            description: Optional description
            term_id: Optional explicit ID (e.g., term.customer)
            
        Returns:
            Created term dictionary
        """
        glossary = self.load()
        
        # Generate ID if not provided
        if not term_id:
            term_id = f"term.{name.lower().replace(' ', '_')}"
        
        # Check if term already exists
        terms = glossary.get("terms", [])
        for term in terms:
            if term.get("id") == term_id or term.get("name") == name:
                raise ValueError(f"Term '{name}' or ID '{term_id}' already exists")
        
        # Create new term
        new_term = {
            "id": term_id,
            "name": name,
            "description": description or "",
            "synonyms": [],
            "owner": "",
            "tags": [],
            "linked_assets": [],
            "linked_columns": [],
        }
        
        terms.append(new_term)
        glossary["terms"] = terms
        
        # Save
        self.save(glossary)
        
        return new_term
    
    def link_term(
        self,
        term_name_or_id: str,
        asset: str,
        column: Optional[str] = None,
        role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Link a glossary term to an asset and optionally a column.
        
        Args:
            term_name_or_id: Term name or ID
            asset: Asset ID or path
            column: Optional column name
            role: Optional role (e.g., primary_key, foreign_key, attribute)
            
        Returns:
            Updated term dictionary
        """
        glossary = self.load()
        
        # Find term
        terms = glossary.get("terms", [])
        term = None
        for t in terms:
            if t.get("id") == term_name_or_id or t.get("name") == term_name_or_id:
                term = t
                break
        
        if not term:
            raise ValueError(f"Term '{term_name_or_id}' not found")
        
        # Update linked assets
        linked_assets = term.get("linked_assets", [])
        if asset not in linked_assets:
            linked_assets.append(asset)
        term["linked_assets"] = linked_assets
        
        # Update linked columns if column specified
        if column:
            linked_columns = term.get("linked_columns", [])
            # Check if already linked
            existing = None
            for lc in linked_columns:
                if lc.get("asset") == asset and lc.get("column") == column:
                    existing = lc
                    break
            
            if existing:
                if role:
                    existing["role"] = role
            else:
                linked_columns.append({
                    "asset": asset,
                    "column": column,
                    "role": role or "",
                })
            
            term["linked_columns"] = linked_columns
        
        # Save
        self.save(glossary)
        
        return term

