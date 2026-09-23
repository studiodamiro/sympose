"""
Persona-profile loading — enough for the vault routes to scope a request to
a persona's allowed folders, plus the shared roster/default-persona
resolution every channel (dashboard, CLI, engine) builds on. The legacy
backend's `ProfileManager` does much more (soul/memory file bootstrapping,
skills, wiki layer) and pulls in the LLM/skills stack just by importing it;
this module deliberately stays free of that — no `litellm` import here, see
`_normalize`'s `model` handling below.
"""

import glob
import os
from typing import Any

import yaml

from sympose import settings_store
from sympose.security import is_safe_path

PERSONA_FILENAME = "persona.yaml"
FACTORY_DEFAULT_PERSONA = "samantha"   # fallback value only — see resolve_default_persona
_DEFAULT_PERSONA_SETTINGS_KEY = "default_persona"


def profiles_dir() -> str:
    return os.getenv("SYMPOSE_PROFILES_DIR") or os.path.join(os.getcwd(), "profiles")


def persona_dir(handle: str) -> str:
    """`<profiles_dir>/<handle>/` — everything belonging to one persona
    (config, and later soul/memory/expertise/sessions) lives here
    (docs/decisions/011). Not checked for safety; callers that touch the
    filesystem run `is_safe_path` against `profiles_dir()` first."""
    return os.path.join(profiles_dir(), handle.lower())


def resolve_default_persona() -> str:
    """The handle used when no persona is specified — user-configurable
    (mirrors `engine/model.py`'s `resolve_model()`), not a hardcoded
    literal: legacy's `runtime.default_persona` config key established
    this same shape. No setter/route exists yet, same as `chat_model`'s
    own settings-store read path today — `settings_store.set` already
    works the moment something needs to call it."""
    return settings_store.get(_DEFAULT_PERSONA_SETTINGS_KEY, FACTORY_DEFAULT_PERSONA)


def set_default_persona(handle: str) -> bool:
    """Makes `handle` the default persona. Refuses (returns `False`) a
    handle that isn't in the roster — storing an unknown one would make
    `resolve_profile` fail closed for every request that doesn't name a
    persona — and lowercases it, since nothing else normalizes case on
    write. Also `False` if the settings file couldn't be written."""
    handle = handle.lower()
    if handle not in {p["handle"] for p in list_profiles()}:
        return False
    return settings_store.set(_DEFAULT_PERSONA_SETTINGS_KEY, handle)


def _normalize(data: dict[str, Any], handle: str) -> dict[str, Any]:
    """Fills in every key a caller might read, so nothing downstream needs
    its own `.get(key, default)` duplication. `model` is left as whatever
    the YAML says, or `None` — deliberately not defaulted to a real model
    id here, since that would mean importing `sympose.engine.model` (which
    `import litellm`s at module scope) into every vault route's request
    path, not just the one place that actually needs a display fallback
    (`server_persona_handlers.get_personas`)."""
    handle = handle.lower()
    return {
        **data,
        "handle": handle,
        "name": data.get("name") or handle.title(),
        "title": data.get("title") or "",
        "model": data.get("model"),
        "skills": data.get("skills") or [],
    }


def _fallback_profile(handle: str) -> dict[str, Any]:
    """Whole-vault default — only for "profiles/ doesn't exist at all", or
    as `resolve_profile`'s last-resort safety net for the factory default
    specifically (see there)."""
    return _normalize({"vault_folders": ["*"]}, handle)


def get_profile(handle: str) -> dict[str, Any] | None:
    """Loads `<profiles_dir>/<handle>/persona.yaml`. Returns the whole-vault
    fallback only when no profiles directory exists yet at all (a fresh
    checkout with no `profiles/`) — the intended day-one default. Once a
    profiles directory exists, an unknown handle, an unsafe/traversal
    path, or a file that fails to parse all return `None`: fail closed,
    not a silent widening to full access."""
    handle = handle.lower()
    base = profiles_dir()
    if not os.path.isdir(base):
        return _fallback_profile(handle)
    path = os.path.join(persona_dir(handle), PERSONA_FILENAME)
    if not is_safe_path(path, base):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    return _normalize(data, handle)


def resolve_profile(persona: str | None) -> dict[str, Any] | None:
    """`persona` resolved to a profile dict, or `None` if it names no
    valid persona. A falsy `persona` resolves through
    `resolve_default_persona()` rather than a hardcoded handle. The
    whole-vault safety net only ever fires for the hardcoded
    `FACTORY_DEFAULT_PERSONA` (the one handle guaranteed to ship
    committed) — a *configured* custom default whose file has gone
    missing fails closed instead of silently falling back to full vault
    access under that orphaned handle, which would reopen the exact bug
    this function exists to close, just via the settings key instead of a
    typo."""
    handle = persona or resolve_default_persona()
    profile = get_profile(handle)
    if profile is not None:
        return profile
    # get_profile already lowercases handle internally for its own file
    # lookup, but this comparison is against the raw handle -- without
    # lowering it here too, a mixed-case configured default (nothing
    # normalizes case on write to settings_store) would never match
    # FACTORY_DEFAULT_PERSONA and silently lose its safety net.
    if handle.lower() == FACTORY_DEFAULT_PERSONA:
        return _fallback_profile(handle)
    return None


def list_profiles() -> list[dict[str, Any]]:
    """Every configured `profiles/<handle>/persona.yaml` handle, normalized the same way
    `get_profile` normalizes a single one — the one canonical roster this
    module owns, shared by the CLI's persona picker and the dashboard's
    `GET /api/personas`. Falls back to a synthetic Samantha entry when no
    profiles directory exists yet, matching `get_profile`'s own fallback;
    an existing-but-empty directory deliberately returns `[]` rather than
    that same synthetic entry, consistent with `get_profile`'s fail-closed
    posture once a profiles directory is actually configured."""
    base = profiles_dir()
    if not os.path.isdir(base):
        return [_fallback_profile(FACTORY_DEFAULT_PERSONA)]
    handles = sorted(
        {
            os.path.basename(os.path.dirname(p)).lower()
            for p in glob.glob(os.path.join(base, "*", PERSONA_FILENAME))
        }
    )
    return [p for h in handles if (p := get_profile(h)) is not None]
