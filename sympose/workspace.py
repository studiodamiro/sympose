"""
Workspace resolution for Sympose.

A dependency-free leaf module (imports only the stdlib) so it can be imported
before anything that reads environment variables at import time — notably
`sympose.config`, which uses it to load the *workspace* `.env` and nothing else.
"""

import os


def resolve_workspace_dir() -> str:
    """
    Resolves the active Sympose workspace directory.
    If 'profiles/' or 'config.yaml' exists in a specific sub-project directory
    (and CWD is not ~ or /), use CWD (Local Project Mode). Otherwise, defaults
    to '~/.sympose' (Global Sovereign User Mode).
    """
    cwd = os.path.abspath(os.getcwd())
    home = os.path.abspath(os.path.expanduser("~"))
    if cwd not in (home, "/", os.path.abspath(os.sep)):
        if os.path.exists(os.path.join(cwd, "profiles")) or os.path.exists(os.path.join(cwd, "config.yaml")):
            return cwd
    return os.path.join(home, ".sympose")
