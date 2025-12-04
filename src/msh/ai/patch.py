"""
Patch Engine for msh.

Safe application of AI-generated changes using JSON Patch format (RFC 6902).
"""
import os
import json
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
from msh.ai.safety import AISafety
from msh.logger import logger


class PatchEngine:
    """Applies patches to .msh files safely."""
    
    def __init__(self):
        """Initialize patch engine."""
        self.safety = AISafety()
    
    def apply_patch(
        self,
        patch_file: Optional[str] = None,
        patch_data: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Apply a patch file or patch data to one or more .msh assets.
        
        Args:
            patch_file: Optional path to JSON patch file
            patch_data: Optional patch data dictionary (if patch_file not provided)
            dry_run: If True, show diff without modifying files
            
        Returns:
            Dictionary with results
        """
        # Load patch data
        if patch_data is None:
            if patch_file is None:
                raise ValueError("Either patch_file or patch_data must be provided")
            with open(patch_file, "r") as f:
                patch_data = json.load(f)
        
        # Validate patch
        is_safe, warnings = self.safety.validate_patch(patch_data)
        if not is_safe:
            raise ValueError(f"Patch contains dangerous operations: {warnings}")
        
        if warnings:
            logger.warning(f"Patch warnings: {warnings}")
        
        # Apply patches
        results = {
            "applied": [],
            "failed": [],
            "diffs": []
        }
        
        patches = patch_data.get("patches", [])
        for patch_op in patches:
            file_path = patch_op.get("file_path")
            operations = patch_op.get("operations", [])
            
            try:
                if dry_run:
                    diff = self._generate_diff(file_path, operations)
                    results["diffs"].append({
                        "file": file_path,
                        "diff": diff
                    })
                else:
                    self._apply_operations(file_path, operations)
                    results["applied"].append(file_path)
            except Exception as e:
                logger.error(f"Failed to apply patch to {file_path}: {e}")
                results["failed"].append({
                    "file": file_path,
                    "error": str(e)
                })
        
        return results
    
    def _apply_operations(self, file_path: str, operations: List[Dict[str, Any]]) -> None:
        """
        Apply JSON Patch operations to a file.
        
        Args:
            file_path: Path to .msh file
            operations: List of JSON Patch operations
        """
        # Load file
        with open(file_path, "r") as f:
            content = f.read()
        
        # Parse YAML
        data = yaml.safe_load(content)
        
        # Apply operations
        for op in operations:
            op_type = op.get("op")
            path = op.get("path")
            value = op.get("value")
            
            if op_type == "add":
                self._json_patch_add(data, path, value)
            elif op_type == "remove":
                self._json_patch_remove(data, path)
            elif op_type == "replace":
                self._json_patch_replace(data, path, value)
            else:
                raise ValueError(f"Unsupported operation: {op_type}")
        
        # Save file
        with open(file_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    def _json_patch_add(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """Add value at path."""
        parts = path.lstrip("/").split("/")
        current = data
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        final_key = parts[-1]
        if final_key == "-":
            # Append to array
            if not isinstance(current, list):
                raise ValueError(f"Cannot append to non-list at {path}")
            current.append(value)
        else:
            current[final_key] = value
    
    def _json_patch_remove(self, data: Dict[str, Any], path: str) -> None:
        """Remove value at path."""
        parts = path.lstrip("/").split("/")
        current = data
        
        for part in parts[:-1]:
            if part not in current:
                return  # Path doesn't exist, ignore
            current = current[part]
        
        final_key = parts[-1]
        if isinstance(current, dict):
            current.pop(final_key, None)
        elif isinstance(current, list):
            try:
                index = int(final_key)
                current.pop(index)
            except (ValueError, IndexError):
                pass
    
    def _json_patch_replace(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """Replace value at path."""
        parts = path.lstrip("/").split("/")
        current = data
        
        for part in parts[:-1]:
            if part not in current:
                raise ValueError(f"Path not found: {path}")
            current = current[part]
        
        final_key = parts[-1]
        if final_key not in current:
            raise ValueError(f"Path not found: {path}")
        
        current[final_key] = value
    
    def _generate_diff(self, file_path: str, operations: List[Dict[str, Any]]) -> str:
        """
        Generate unified diff for dry-run mode.
        
        Args:
            file_path: Path to file
            operations: List of operations
            
        Returns:
            Diff string
        """
        # Load original file
        with open(file_path, "r") as f:
            original_lines = f.readlines()
        
        # For now, return a simple summary
        # A full diff implementation would require more complex logic
        diff_lines = [f"--- {file_path}\n", f"+++ {file_path}\n"]
        
        for op in operations:
            op_type = op.get("op")
            path = op.get("path")
            if op_type == "add":
                diff_lines.append(f"+ Add at {path}\n")
            elif op_type == "remove":
                diff_lines.append(f"- Remove at {path}\n")
            elif op_type == "replace":
                diff_lines.append(f"~ Replace at {path}\n")
        
        return "".join(diff_lines)

