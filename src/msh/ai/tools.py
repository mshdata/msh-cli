"""
AI Tool Functions for msh.

Pluggable functions for LLM function calling (OpenAI tools format).
"""
from typing import Dict, Any, List, Optional
from msh.ai.metadata_cache import MetadataCache
from msh.ai.manifest import ManifestGenerator
from msh.glossary.glossary import Glossary


# Tool schemas (JSON Schema format for OpenAI tools)
TOOL_SCHEMAS = {
    "asset_search": {
        "type": "function",
        "function": {
            "name": "asset_search",
            "description": "Search for assets by id, name, or description",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["query"]
            }
        }
    },
    "schema_lookup": {
        "type": "function",
        "function": {
            "name": "schema_lookup",
            "description": "Return schema for an asset",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {
                        "type": "string",
                        "description": "Asset ID"
                    }
                },
                "required": ["asset_id"]
            }
        }
    },
    "lineage_lookup": {
        "type": "function",
        "function": {
            "name": "lineage_lookup",
            "description": "Return upstream and downstream lineage for an asset",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {
                        "type": "string",
                        "description": "Asset ID"
                    }
                },
                "required": ["asset_id"]
            }
        }
    },
    "glossary_search": {
        "type": "function",
        "function": {
            "name": "glossary_search",
            "description": "Search glossary terms by name, synonyms, or description",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["query"]
            }
        }
    },
    "generate_msh_skeleton": {
        "type": "function",
        "function": {
            "name": "generate_msh_skeleton",
            "description": "Generate a minimal .msh asset skeleton with given parameters",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_name": {
                        "type": "string",
                        "description": "Asset name"
                    },
                    "purpose": {
                        "type": "string",
                        "description": "Asset purpose"
                    },
                    "upstream_assets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Upstream asset IDs"
                    }
                },
                "required": ["asset_name", "purpose"]
            }
        }
    },
    "validate_asset": {
        "type": "function",
        "function": {
            "name": "validate_asset",
            "description": "Run static validations on an asset and report issues",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {
                        "type": "string",
                        "description": "Asset ID"
                    }
                },
                "required": ["asset_id"]
            }
        }
    }
}


class AITools:
    """AI tool implementations."""
    
    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize AI tools.
        
        Args:
            project_root: Project root directory
        """
        import os
        if project_root is None:
            project_root = os.getcwd()
        
        self.project_root = project_root
        self.cache = MetadataCache(project_root=project_root)
        self.manifest_gen = ManifestGenerator(project_root=project_root)
        self.glossary = Glossary(project_root=project_root)
    
    def asset_search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for assets by id, name, or description.
        
        Args:
            query: Search query
            
        Returns:
            List of asset summaries
        """
        manifest = self.cache.load_manifest()
        if not manifest:
            manifest = self.manifest_gen.generate_manifest()
        
        assets = manifest.get("assets", [])
        query_lower = query.lower()
        
        results = []
        for asset in assets:
            asset_id = asset.get("id", "").lower()
            path = asset.get("path", "").lower()
            
            if query_lower in asset_id or query_lower in path:
                results.append({
                    "id": asset.get("id"),
                    "path": asset.get("path"),
                    "blocks": list(asset.get("blocks", {}).keys())
                })
        
        return results
    
    def schema_lookup(self, asset_id: str) -> Dict[str, Any]:
        """
        Return schema for an asset.
        
        Args:
            asset_id: Asset ID
            
        Returns:
            Schema dictionary
        """
        manifest = self.cache.load_manifest()
        if not manifest:
            manifest = self.manifest_gen.generate_manifest()
        
        for asset in manifest.get("assets", []):
            if asset.get("id") == asset_id:
                return asset.get("schema", {})
        
        return {}
    
    def lineage_lookup(self, asset_id: str) -> Dict[str, Any]:
        """
        Return upstream and downstream lineage for an asset.
        
        Args:
            asset_id: Asset ID
            
        Returns:
            Lineage dictionary with upstream and downstream lists
        """
        lineage = self.cache.load_lineage()
        if not lineage:
            lineage = self.manifest_gen.generate_lineage()
        
        edges = lineage.get("edges", [])
        upstream = [e.get("from") for e in edges if e.get("to") == asset_id]
        downstream = [e.get("to") for e in edges if e.get("from") == asset_id]
        
        return {
            "upstream": upstream,
            "downstream": downstream
        }
    
    def glossary_search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search glossary terms by name, synonyms, or description.
        
        Args:
            query: Search query
            
        Returns:
            List of glossary term summaries
        """
        glossary_data = self.glossary.load()
        terms = glossary_data.get("terms", [])
        query_lower = query.lower()
        
        results = []
        for term in terms:
            name = term.get("name", "").lower()
            description = term.get("description", "").lower()
            synonyms = [s.lower() for s in term.get("synonyms", [])]
            
            if (query_lower in name or 
                query_lower in description or 
                any(query_lower in syn for syn in synonyms)):
                results.append({
                    "id": term.get("id"),
                    "name": term.get("name"),
                    "description": term.get("description", "")[:100]  # Truncate
                })
        
        return results
    
    def generate_msh_skeleton(
        self,
        asset_name: str,
        purpose: str,
        upstream_assets: Optional[List[str]] = None
    ) -> str:
        """
        Generate a minimal .msh asset skeleton.
        
        Args:
            asset_name: Asset name
            purpose: Asset purpose
            upstream_assets: Optional list of upstream asset IDs
            
        Returns:
            YAML string for .msh file
        """
        import yaml
        
        skeleton = {
            "id": asset_name,
            "description": purpose,
            "ingest": {
                "type": "sql_database",
                "table": "source_table"
            },
            "transform": f"SELECT * FROM {{ source }}"
        }
        
        if upstream_assets:
            # Add ref() calls for upstream assets
            refs = ", ".join([f"{{{{ ref('{up}') }}}}" for up in upstream_assets])
            skeleton["transform"] = f"SELECT * FROM {refs}"
        
        return yaml.dump(skeleton, default_flow_style=False)
    
    def validate_asset(self, asset_id: str) -> List[Dict[str, Any]]:
        """
        Run static validations on an asset.
        
        Args:
            asset_id: Asset ID
            
        Returns:
            List of validation issues
        """
        issues = []
        
        manifest = self.cache.load_manifest()
        if not manifest:
            manifest = self.manifest_gen.generate_manifest()
        
        # Find asset
        asset = None
        for a in manifest.get("assets", []):
            if a.get("id") == asset_id:
                asset = a
                break
        
        if not asset:
            return [{
                "severity": "error",
                "message": f"Asset '{asset_id}' not found"
            }]
        
        # Basic validations
        blocks = asset.get("blocks", {})
        if "ingest" not in blocks:
            issues.append({
                "severity": "error",
                "message": "Missing ingest block"
            })
        
        if "transform" not in blocks:
            issues.append({
                "severity": "error",
                "message": "Missing transform block"
            })
        
        transform = blocks.get("transform", {})
        sql = transform.get("sql", "")
        if not sql or sql.strip() == "":
            issues.append({
                "severity": "error",
                "message": "Transform SQL is empty"
            })
        
        return issues


def get_tool_schemas() -> List[Dict[str, Any]]:
    """
    Get all tool schemas for LLM function calling.
    
    Returns:
        List of tool schema dictionaries
    """
    return list(TOOL_SCHEMAS.values())

