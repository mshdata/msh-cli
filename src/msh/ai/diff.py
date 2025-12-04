"""
Diff Generation for msh.

Generates unified diffs for patches and changes.
"""
import difflib
from typing import List


def generate_unified_diff(
    original: str,
    modified: str,
    file_path: str = "file"
) -> str:
    """
    Generate unified diff between two strings.
    
    Args:
        original: Original content
        modified: Modified content
        file_path: File path for diff header
        
    Returns:
        Unified diff string
    """
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"{file_path}",
        tofile=f"{file_path}",
        lineterm=""
    )
    
    return "".join(diff)

