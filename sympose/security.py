"""Sandbox path containment, lifted from the legacy `config.py` (which pulls
in the whole LLM/config-manager stack just to host this one pure function)."""

import os


def is_safe_path(target_path: str, base_dir: str = ".") -> bool:
    """Prevents directory traversal attacks (e.g. ../../etc/passwd), sibling
    directory bypasses, and symlink escapes (resolves symlinks before
    comparing)."""
    try:
        resolved_target = os.path.realpath(target_path)
        resolved_base = os.path.realpath(base_dir)
        return os.path.commonpath([resolved_target, resolved_base]) == resolved_base
    except Exception:
        return False
