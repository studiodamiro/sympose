"""
Persona-profile loading — enough for the vault routes to scope a request to
a persona's allowed folders, plus the shared roster/default-persona
resolution every channel (web app, CLI, engine) builds on. The legacy
backend's `ProfileManager` does much more (soul/memory file bootstrapping,
skills, wiki layer) and pulls in the LLM/skills stack just by importing it;
this module deliberately stays free of that — no `litellm` import here, see
`_normalize`'s `model` handling below.
"""

import glob
import logging
import os
from typing import Any

import yaml

from sympose import settings_store
from sympose.security import is_safe_path

log = logging.getLogger(__name__)

PERSONA_FILENAME = "persona.yaml"
SOUL_FILENAME = "soul.md"
FACTORY_DEFAULT_PERSONA = "samantha"   # fallback value only — see resolve_default_persona
_DEFAULT_PERSONA_SETTINGS_KEY = "default_persona"


def profiles_dir() -> str:
    return os.getenv("SYMPOSE_PROFILES_DIR") or os.path.join(os.getcwd(), "profiles")


def persona_dir(handle: str) -> str:
    """`<profiles_dir>/<handle>/` — everything belonging to one persona
    (config, and later soul/memory/expertise/sessions) lives here
    (docs/decisions/011). Raises `ValueError` unless `handle` is a single
    plain path component: `is_safe_path` alone only proves a path stays
    inside `profiles/`, which `.` (the directory itself) and `a/b` (a
    nested path) both do without naming one persona's own directory."""
    handle = handle.lower()
    if handle in ("", ".", "..") or os.path.basename(handle) != handle:
        raise ValueError(f"Not a valid persona handle: {handle!r}")
    return os.path.join(profiles_dir(), handle)


def load_soul(handle: str) -> str | None:
    """The persona's `soul.md` text (docs/decisions/012), or `None` when it
    has none — missing, empty, unsafe path, or unreadable — so the caller
    can fall back to a generic soul. Read on demand rather than inside
    `get_profile`, which runs on every vault route that has no use for it;
    an edit to the file takes effect on the next call."""
    try:
        path = os.path.join(persona_dir(handle), SOUL_FILENAME)
    except ValueError:
        return None
    if not is_safe_path(path, profiles_dir()):
        return None
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read().strip() or None
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as e:
        log.warning("Couldn't read %s, using the default soul: %s", path, e)
        return None


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


def _aliases(value: Any) -> list[str]:
    """The other names a persona is called by (`aliases:` in persona.yaml): a
    list of names, or a single name. Anything else, and blank entries, are
    ignored rather than failing the persona."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [name.strip() for name in value if isinstance(name, str) and name.strip()]


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
        "aliases": _aliases(data.get("aliases")),
        # Whether the persona has the Sympose reference library (docs/decisions/022):
        # an explicit true; and the shipped default persona unless it says otherwise, so a
        # `persona.yaml` written before the key existed does not lose it.
        "sympose_reference": data.get("sympose_reference") is True
        or (data.get("sympose_reference") is None and handle == FACTORY_DEFAULT_PERSONA),
    }


def _fallback_profile(handle: str) -> dict[str, Any]:
    """Whole-vault default — only for "profiles/ doesn't exist at all", or
    as `resolve_profile`'s last-resort safety net for the factory default
    specifically (see there)."""
    return _normalize(
        {"vault_folders": ["*"], "sympose_reference": handle.lower() == FACTORY_DEFAULT_PERSONA}, handle
    )


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
    try:
        path = os.path.join(persona_dir(handle), PERSONA_FILENAME)
    except ValueError:
        return None
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
    module owns, shared by the CLI's persona picker and the web app's
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


def reference_persona_names() -> list[str]:
    """The display names of the personas that have the Sympose reference
    library, for the ones that do not to point the user to (docs/decisions/022)."""
    return [str(p["name"]) for p in list_profiles() if p.get("sympose_reference")]
