"""
AST Generator for msh assets.

Converts .msh files into structured Abstract Syntax Tree (AST) representation
for AI consumption and analysis.
"""
import re
import jinja2
from jinja2 import nodes
from typing import Dict, Any, List, Optional, Set
from pathlib import Path


class AstGenerator:
    """Generates AST from parsed .msh asset data."""
    
    def __init__(self):
        """Initialize the AST generator."""
        self.jinja_env = jinja2.Environment()
    
    def generate_ast(self, asset_data: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """
        Generate AST from parsed asset data.
        
        Args:
            asset_data: Parsed .msh file data
            file_path: Path to the .msh file
            
        Returns:
            Dictionary containing structured AST blocks
        """
        ast = {
            "id": self._extract_asset_id(asset_data, file_path),
            "path": str(file_path),
            "blocks": {}
        }
        
        # Extract ingest block
        if "ingest" in asset_data:
            ast["blocks"]["ingest"] = self._extract_ingest_block(asset_data["ingest"])
        
        # Extract transform block
        if "transform" in asset_data:
            ast["blocks"]["transform"] = self._extract_transform_block(asset_data["transform"])
        
        # Extract contract block
        if "contract" in asset_data:
            ast["blocks"]["contract"] = asset_data["contract"]
        
        # Extract deploy block (if exists)
        if "deploy" in asset_data:
            ast["blocks"]["deploy"] = asset_data["deploy"]
        
        # Extract tests
        if "tests" in asset_data:
            ast["tests"] = asset_data["tests"]
        else:
            ast["tests"] = []
        
        return ast
    
    def _extract_asset_id(self, asset_data: Dict[str, Any], file_path: str) -> str:
        """Extract asset ID from data or file path."""
        if "id" in asset_data:
            return asset_data["id"]
        if "name" in asset_data:
            return asset_data["name"]
        # Fallback to filename without extension
        return Path(file_path).stem
    
    def _extract_ingest_block(self, ingest: Any) -> Dict[str, Any]:
        """Extract structured ingest block information."""
        if isinstance(ingest, dict):
            return {
                "type": ingest.get("type"),
                "source": ingest.get("source"),
                "table": ingest.get("table"),
                "resource": ingest.get("resource"),
                "endpoint": ingest.get("endpoint"),
                "credentials": self._sanitize_credentials(ingest.get("credentials")),
                "config": ingest.get("config", {}),
                "write_disposition": ingest.get("write_disposition"),
                "primary_key": ingest.get("primary_key"),
            }
        return {"raw": str(ingest)}
    
    def _sanitize_credentials(self, credentials: Any) -> Optional[Dict[str, Any]]:
        """Sanitize credentials by removing sensitive values."""
        if not isinstance(credentials, dict):
            return None
        
        sanitized = {}
        for key, value in credentials.items():
            # Mask sensitive fields
            if key.lower() in ["password", "passwd", "secret", "api_key", "token", "key"]:
                sanitized[key] = "***MASKED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_credentials(value)
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _extract_transform_block(self, transform: str) -> Dict[str, Any]:
        """Extract structured transform block information."""
        if not isinstance(transform, str):
            return {"raw": str(transform)}
        
        # Extract dependencies via {{ ref() }}
        dependencies = self._extract_dependencies(transform)
        
        # Extract schema information (columns referenced)
        columns = self._extract_columns_from_sql(transform)
        
        return {
            "sql": transform,
            "dependencies": dependencies,
            "columns_referenced": columns,
            "has_joins": self._has_joins(transform),
            "has_aggregations": self._has_aggregations(transform),
        }
    
    def _extract_dependencies(self, sql: str) -> List[str]:
        """Extract asset dependencies from SQL using Jinja2 AST."""
        dependencies: Set[str] = set()
        
        try:
            ast = self.jinja_env.parse(sql)
            # Find all function calls
            for call in ast.find_all(nodes.Call):
                # Check if the call is to 'ref'
                if isinstance(call.node, nodes.Name) and call.node.name == 'ref':
                    # Extract arguments
                    if call.args:
                        # The model name is the last argument
                        last_arg = call.args[-1]
                        if isinstance(last_arg, nodes.Const):
                            ref_name = last_arg.value
                            dependencies.add(ref_name)
        except (jinja2.TemplateSyntaxError, jinja2.UndefinedError, AttributeError, TypeError):
            # Fallback to regex if Jinja parsing fails
            pattern = r"\{\{\s*ref\(['\"]([^'\"]+)['\"]\)\s*\}\}"
            matches = re.findall(pattern, sql)
            dependencies.update(matches)
        
        return sorted(list(dependencies))
    
    def _extract_columns_from_sql(self, sql: str) -> List[str]:
        """Extract column names from SQL (basic extraction)."""
        columns: Set[str] = set()
        
        # Simple regex to find column references (not perfect but works for common cases)
        # Match patterns like: column_name, table.column_name, "column_name"
        patterns = [
            r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*[,=]',  # column_name followed by comma or equals
            r'\.([a-zA-Z_][a-zA-Z0-9_]*)',  # .column_name
            r'"([^"]+)"',  # "column_name"
            r"'([^']+)'",  # 'column_name'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            columns.update(matches)
        
        # Filter out SQL keywords
        sql_keywords = {
            'select', 'from', 'where', 'group', 'by', 'order', 'having',
            'join', 'inner', 'left', 'right', 'outer', 'on', 'as', 'and', 'or',
            'not', 'in', 'exists', 'case', 'when', 'then', 'else', 'end',
            'union', 'all', 'distinct', 'limit', 'offset', 'null', 'true', 'false'
        }
        
        filtered = [col for col in columns if col.lower() not in sql_keywords]
        return sorted(list(set(filtered)))
    
    def _has_joins(self, sql: str) -> bool:
        """Check if SQL contains JOIN operations."""
        join_patterns = [
            r'\bJOIN\b',
            r'\bINNER\s+JOIN\b',
            r'\bLEFT\s+JOIN\b',
            r'\bRIGHT\s+JOIN\b',
            r'\bFULL\s+JOIN\b',
        ]
        sql_upper = sql.upper()
        return any(re.search(pattern, sql_upper) for pattern in join_patterns)
    
    def _has_aggregations(self, sql: str) -> bool:
        """Check if SQL contains aggregation functions."""
        agg_patterns = [
            r'\bCOUNT\s*\(',
            r'\bSUM\s*\(',
            r'\bAVG\s*\(',
            r'\bMIN\s*\(',
            r'\bMAX\s*\(',
            r'\bGROUP\s+BY\b',
        ]
        sql_upper = sql.upper()
        return any(re.search(pattern, sql_upper) for pattern in agg_patterns)

