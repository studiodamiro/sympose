"""
Minimal persona-profile loading — just enough for the vault routes to scope
a request to a persona's allowed folders. The legacy backend's
`ProfileManager` does much more (soul/memory file bootstrapping, skills,
wiki layer) and pulls in the LLM/skills stack just by importing it; the
vault routes only ever read `vault_folders` / `vault_folder` off the
returned dict, so a plain YAML load is a complete substitute here.
"""

import os

import yaml

from sympose.security import is_safe_path


def profiles_dir() -> str:
    return os.getenv("SYMPOSE_PROFILES_DIR") or os.path.join(os.getcwd(), "profiles")


def get_profile(handle: str) -> dict:
    """Loads `<profiles_dir>/<handle>.yaml`. Falls back to a whole-vault
    "samantha" profile when no profiles directory / file exists yet (a
    fresh checkout with no `profiles/`), when `handle` resolves outside
    `profiles_dir()` (rejected before ever opening anything — the same
    containment check every vault path goes through), or when the file
    exists but fails to load."""
    base = profiles_dir()
    path = os.path.join(base, f"{handle.lower()}.yaml")
    if is_safe_path(path, base):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                return data
        except (OSError, yaml.YAMLError):
            pass
    return {"handle": handle.lower(), "vault_folders": ["*"]}


def resolve_profile(persona: str | None) -> dict:
    return get_profile(persona) if persona else get_profile("samantha")
