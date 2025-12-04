"""
AI Safety Layer for msh.

Blocks dangerous AI-generated operations and validates output.
"""
import re
from typing import Dict, Any, List, Optional
from msh.logger import logger


class AISafety:
    """AI safety filters and validators."""
    
    # Blocked patterns (destructive operations)
    BLOCKED_PATTERNS = [
        r"DROP\s+TABLE",
        r"TRUNCATE\s+TABLE",
        r"DELETE\s+FROM",
        r"ALTER\s+TABLE\s+.*\s+DROP\s+COLUMN",
    ]
    
    # Soft warnings (potentially problematic but not blocked)
    WARNING_PATTERNS = [
        r"SELECT\s+\*",
        r"UNION\s+ALL\s+.*\s+without\s+dedupe",
        r"CROSS\s+JOIN",
    ]
    
    def __init__(self):
        """Initialize AI safety layer."""
        self.blocked_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.BLOCKED_PATTERNS]
        self.warning_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.WARNING_PATTERNS]
    
    def validate_sql(self, sql: str) -> tuple[bool, List[str]]:
        """
        Validate SQL for dangerous patterns.
        
        Args:
            sql: SQL string to validate
            
        Returns:
            Tuple of (is_safe, warnings)
        """
        warnings = []
        
        # Check blocked patterns
        for pattern in self.blocked_regex:
            if pattern.search(sql):
                logger.error(f"Blocked dangerous SQL pattern: {pattern.pattern}")
                return False, ["Blocked dangerous operation detected"]
        
        # Check warning patterns
        for pattern in self.warning_regex:
            if pattern.search(sql):
                warnings.append(f"Potentially problematic pattern: {pattern.pattern}")
        
        return True, warnings
    
    def validate_patch(self, patch: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate patch for dangerous operations.
        
        Args:
            patch: Patch dictionary (JSON Patch format)
            
        Returns:
            Tuple of (is_safe, warnings)
        """
        warnings = []
        operations = patch.get("patches", [])
        
        for patch_op in operations:
            file_path = patch_op.get("file_path", "")
            operations_list = patch_op.get("operations", [])
            
            for op in operations_list:
                op_type = op.get("op")
                path = op.get("path", "")
                value = op.get("value")
                
                # Check for dangerous operations
                if op_type == "remove" and "transform" in path.lower():
                    warnings.append(f"Removing transform block in {file_path}")
                
                # Check value for SQL if it's a transform block
                if isinstance(value, str) and "transform" in path.lower():
                    is_safe, sql_warnings = self.validate_sql(value)
                    if not is_safe:
                        return False, sql_warnings
                    warnings.extend(sql_warnings)
        
        return True, warnings
    
    def check_pii_policy(self, asset: Dict[str, Any], glossary_policies: List[Dict[str, Any]]) -> List[str]:
        """
        Check asset against PII policies from glossary.
        
        Args:
            asset: Asset dictionary
            glossary_policies: List of glossary policy dictionaries
            
        Returns:
            List of policy violations
        """
        violations = []
        
        # Check if asset is marked as public
        is_public = asset.get("deploy", {}).get("public", False)
        
        if not is_public:
            return violations
        
        # Check policies
        for policy in glossary_policies:
            rules = policy.get("rules", [])
            applies_to = policy.get("applies_to", [])
            
            # Check if policy applies to this asset
            asset_id = asset.get("id")
            applies = False
            for app in applies_to:
                if app.get("asset") == asset_id:
                    applies = True
                    break
            
            if not applies:
                continue
            
            # Check rules
            for rule in rules:
                if "llm_context:" in rule:
                    # This is an LLM context rule
                    if "no_pii" in rule.lower() or "pii" in rule.lower():
                        violations.append(f"Policy '{policy.get('name')}' prohibits PII in public assets")
        
        return violations
    
    def mask_pii_in_context(self, context: Dict[str, Any], glossary_policies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Mask or omit PII columns in context packs based on glossary policies.
        
        Args:
            context: Context pack dictionary
            glossary_policies: List of glossary policy dictionaries
            
        Returns:
            Masked context pack
        """
        masked_context = context.copy()
        
        # Find PII columns from schemas
        assets = masked_context.get("assets", [])
        for asset in assets:
            schema = asset.get("schema", {})
            columns = schema.get("columns", [])
            
            # Check policies for this asset
            asset_id = asset.get("id")
            pii_columns = set()
            
            for policy in glossary_policies:
                applies_to = policy.get("applies_to", [])
                for app in applies_to:
                    if app.get("asset") == asset_id:
                        column_name = app.get("column")
                        if column_name:
                            pii_columns.add(column_name)
            
            # Filter out PII columns
            if pii_columns:
                schema["columns"] = [
                    col for col in columns
                    if col.get("name") not in pii_columns
                ]
                schema["_pii_masked"] = True
        
        return masked_context

