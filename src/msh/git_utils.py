"""
Git utilities for msh.

Provides git-aware functionality for schema isolation during development.
"""
import subprocess
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_current_branch() -> Optional[str]:
    """
    Gets the current git branch name.
    
    Returns:
        Branch name string, or None if not in a git repo or git command fails.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        branch = result.stdout.strip()
        if branch:
            return branch
        return None
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        # Not a git repo, git not installed, or command failed
        logger.debug(f"Could not get git branch: {e}")
        return None
    except Exception as e:
        # Unexpected error
        logger.warning(f"Unexpected error getting git branch: {e}")
        return None


def get_sanitized_schema_suffix(branch: Optional[str] = None) -> str:
    """
    Gets a sanitized schema suffix from git branch name.
    
    Args:
        branch: Optional branch name. If None, will attempt to detect current branch.
                 If detection fails, defaults to 'local'.
    
    Returns:
        Sanitized suffix string suitable for use in database schema names.
        - Replaces '/', '-', '.' with '_'
        - Truncates to 20 characters
        - Converts to lowercase
        - Defaults to 'local' if branch is None or detection fails
    
    Examples:
        >>> get_sanitized_schema_suffix("feature/new-api")
        'feature_new_api'
        >>> get_sanitized_schema_suffix(None)
        'local'
        >>> get_sanitized_schema_suffix("very-long-branch-name-that-exceeds-limit")
        'very_long_branch_name'
    """
    if branch is None:
        branch = get_current_branch()
    
    if branch is None:
        return "local"
    
    # Sanitize: replace /, -, . with _
    sanitized = re.sub(r'[/\-\.]', '_', branch)
    
    # Convert to lowercase
    sanitized = sanitized.lower()
    
    # Truncate to 20 characters to avoid DB schema name limits
    # (Some DBs have 63 char limit, but we want to leave room for base schema name)
    if len(sanitized) > 20:
        sanitized = sanitized[:20]
    
    # Remove any trailing underscores from truncation
    sanitized = sanitized.rstrip('_')
    
    # If empty after sanitization, default to local
    if not sanitized:
        return "local"
    
    return sanitized

