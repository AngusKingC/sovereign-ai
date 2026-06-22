"""Path validation to prevent directory traversal attacks.

Single responsibility: Validate file paths to block access outside allowed directories.
"""

from __future__ import annotations

import os
from pathlib import Path


# Sensitive paths that should never be accessible
_BLOCKED_PATHS = [
    "/etc/shadow",
    "/etc/passwd",
    "/etc/sudoers",
    "/proc",
    "/sys",
]


def validate_path(path: str, allowed_base: str | None = None) -> str:
    """Validate a file path to prevent directory traversal.

    Resolves the path to its canonical form (resolving symlinks and ..)
    and checks it doesn't escape allowed boundaries or access sensitive files.

    Args:
        path: The path to validate
        allowed_base: Optional base directory to restrict access to.
            If provided, the resolved path must be under this directory.

    Returns:
        The resolved absolute path

    Raises:
        ValueError: If the path is invalid, contains traversal sequences
            that escape the allowed base, or targets a sensitive system path
    """
    if not path or not isinstance(path, str):
        raise ValueError("Path must be a non-empty string")

    # Resolve to absolute canonical path
    resolved = str(Path(path).resolve())

    # Check against blocked sensitive paths
    for blocked in _BLOCKED_PATHS:
        if resolved == blocked or resolved.startswith(blocked + os.sep):
            raise ValueError(
                f"Access to '{resolved}' is blocked for security reasons"
            )

    # If an allowed base is specified, enforce containment
    if allowed_base is not None:
        base_resolved = str(Path(allowed_base).resolve())
        if not (resolved == base_resolved or resolved.startswith(base_resolved + os.sep)):
            raise ValueError(
                f"Path '{path}' resolves outside the allowed directory '{allowed_base}'"
            )

    return resolved
