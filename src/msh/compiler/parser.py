"""
Parser module for msh compiler.

Handles parsing of .msh files and SQL column extraction for Smart Ingest.
"""
import yaml
import hashlib
import re
import os
from pathlib import Path
from typing import Optional, List, Tuple, Union, Dict, Any
from msh.logger import logger as console
from msh.utils.config import resolve_source, expand_test_suites, apply_defaults


class MshParser:
    """Parses .msh files and extracts SQL columns for Smart Ingest."""
    
    def __init__(self, msh_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the parser.
        
        Args:
            msh_config: Optional configuration dictionary from msh.yaml for source resolution
        """
        self.msh_config: Dict[str, Any] = msh_config or {}
    
    def parse_file(self, file_path: Union[str, Path]) -> Tuple[dict, str]:
        """
        Reads YAML and separates ingest/transform.
        
        Args:
            file_path: Path to the .msh file
            
        Returns:
            Tuple of (parsed_data, content_hash)
            
        Raises:
            ValueError: If file parsing fails
        """
        with open(file_path, "r") as f:
            content = f.read()
        
        # Calculate hash of the content for Blue/Green
        content_hash = hashlib.md5(content.encode()).hexdigest()[:4]
        
        # Check for Frontmatter (SQL-First)
        # Matches /* --- CONFIG --- ... --- */
        # Relaxed regex to handle whitespace/newlines
        pattern = r"^/\*\s*--- CONFIG ---\s*\n(.*?)\n---\s*\*/\s*\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)
        
        if match:
            yaml_text = match.group(1)
            sql_body = match.group(2)
            try:
                data = yaml.safe_load(yaml_text)
            except yaml.YAMLError as e:
                raise ValueError(f"Error parsing Frontmatter in {file_path}: {e}")
            
            # Set transform to the SQL body
            data["transform"] = sql_body.strip()
            
        else:
            # Standard YAML-First
            try:
                data = yaml.safe_load(content)
            except yaml.YAMLError as e:
                raise ValueError(f"Error parsing {file_path}: {e}")
            
            # Task: External SQL Support (transform_file)
            transform = data.get("transform")
            transform_file = data.get("transform_file")
            
            if transform and transform_file:
                raise ValueError(f"Error in {file_path}: Cannot specify both 'transform' and 'transform_file'.")
                
            if transform_file:
                # Resolve path relative to .msh file
                base_dir = os.path.dirname(file_path)
                sql_path = os.path.join(base_dir, transform_file)
                
                if not os.path.exists(sql_path):
                    raise ValueError(f"Error in {file_path}: transform_file '{transform_file}' not found at {sql_path}")
                    
                with open(sql_path, "r") as f:
                    sql_content = f.read()
                    
                data["transform"] = sql_content
                # Update hash to include the SQL content
                # We append the SQL content to the original content string for hashing purposes
                content += sql_content
                content_hash = hashlib.md5(content.encode()).hexdigest()[:4]
            
        # Resolve source references if ingest block uses source reference syntax
        if "ingest" in data and isinstance(data["ingest"], dict):
            ingest = data["ingest"]
            
            # Check if using new source reference syntax
            if "source" in ingest:
                # Validate: can't have both source reference and direct credentials
                if "type" in ingest or "credentials" in ingest:
                    raise ValueError(
                        f"Error in {file_path}: Cannot specify both 'source' reference and "
                        f"direct 'type'/'credentials' in ingest block. Use either source reference "
                        f"or direct credentials, not both."
                    )
                
                # Resolve source reference
                source_name = ingest["source"]
                table_name = ingest.get("table")
                resource_name = ingest.get("resource")
                
                if not table_name and not resource_name:
                    raise ValueError(
                        f"Error in {file_path}: Source reference requires either 'table' "
                        f"(for SQL sources) or 'resource' (for API sources)"
                    )
                
                try:
                    resolved_ingest = resolve_source(
                        source_name=source_name,
                        table_name=table_name,
                        resource_name=resource_name,
                        msh_config=self.msh_config
                    )
                    # Merge any additional fields from the original ingest block
                    # (e.g., write_disposition, primary_key, etc.)
                    for key, value in ingest.items():
                        if key not in ["source", "table", "resource"]:
                            resolved_ingest[key] = value
                    data["ingest"] = resolved_ingest
                except ValueError as e:
                    raise ValueError(f"Error in {file_path}: {e}")
            
        # Expand test suites if present
        if "test_suites" in data:
            test_suites = data.get("test_suites", [])
            if not isinstance(test_suites, list):
                raise ValueError(
                    f"Error in {file_path}: 'test_suites' must be a list of suite names"
                )
            
            try:
                expanded_tests = expand_test_suites(test_suites, self.msh_config)
                # Merge with individual tests if present
                individual_tests = data.get("tests", [])
                if not isinstance(individual_tests, list):
                    individual_tests = []
                
                # Combine expanded suite tests with individual tests
                all_tests = expanded_tests + individual_tests
                data["tests"] = all_tests
                # Remove test_suites field as it's been expanded
                del data["test_suites"]
            except ValueError as e:
                raise ValueError(f"Error in {file_path}: {e}")
        
        # Apply config defaults based on layer
        try:
            data = apply_defaults(data, self.msh_config, file_path)
        except ValueError as e:
            raise ValueError(f"Error in {file_path}: {e}")
            
        return data, content_hash
    
    def extract_columns(self, sql: str) -> Optional[List[str]]:
        """
        Smart Ingest: Uses sqlglot to find columns in SELECT ... FROM {{ source }}
        
        Args:
            sql: SQL query string
            
        Returns:
            List of column names, or None if extraction fails or SELECT * is used
        """
        try:
            import sqlglot
            from sqlglot import exp
        except ImportError:
            console.warning("sqlglot not found. Smart Ingest optimization disabled.")
            return None

        # Pre-process: Replace {{ source }} with a dummy table so sqlglot can parse it
        # sqlglot might choke on Jinja, so we replace {{ source }} with __source__
        sql_clean = sql.replace("{{ source }}", "__source__")
        
        try:
            parsed = sqlglot.parse_one(sql_clean)
        except Exception as e:
            console.warning(f"Failed to parse SQL for Smart Ingest: {e}")
            # Fallback: Regex
            # Matches SELECT col1, col2 FROM __source__
            # Very basic, but better than nothing
            match = re.search(r"SELECT\s+(.*?)\s+FROM\s+__source__", sql_clean, re.IGNORECASE | re.DOTALL)
            if match:
                cols_str = match.group(1)
                # Remove comments?
                # Split by comma
                cols = [c.strip() for c in cols_str.split(",")]
                # Filter out *
                cols = [c for c in cols if c != "*"]
                return cols
            return None
            
        # Check if it's a SELECT statement
        if not isinstance(parsed, exp.Select):
            return None
            
        # Check if it selects from __source__
        # We look at the FROM clause
        # This is a simple heuristic. If there are joins, it might be complex.
        # But for Smart Ingest, we usually expect `SELECT ... FROM {{ source }}` as the main structure.
        
        from_table = parsed.find(exp.Table)
        if not from_table or from_table.name != "__source__":
            # Maybe it's aliased? "FROM __source__ AS s"
            # sqlglot handles this, find(exp.Table) should find it.
            # If the first table is not source, maybe we abort to be safe.
            return None
            
        columns = []
        for expression in parsed.expressions:
            if isinstance(expression, exp.Star):
                return None # SELECT * -> Ingest all
            
            if isinstance(expression, exp.Column):
                columns.append(expression.name)
            elif isinstance(expression, exp.Alias):
                # SELECT col AS alias
                # We want the source column name? Or the alias?
                # Smart Ingest filters the SOURCE. So we need the column being selected from source.
                # If it's `col AS alias`, we need `col`.
                # If it's `func(col) AS alias`, we can't push that down easily to source filtering 
                # unless source supports it.
                # For now, we only support direct columns.
                
                child = expression.this
                if isinstance(child, exp.Column):
                    columns.append(child.name)
                else:
                    # Complex expression, can't optimize safely
                    return None
            else:
                # Complex expression
                return None
                
        return columns

