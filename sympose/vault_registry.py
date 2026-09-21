"""
The configured/active vault list — split out of `vault_paths.py` (project's
200-LOC-per-file guideline) to keep that module scoped to sandbox path
resolution. `VAULT_PATHS` (comma-separated; a single path still works
unchanged) plus any vault added at runtime through the workspace switcher
(ADR 004, persisted as `settings_store`'s `added_vaults`) make up the
configured list; one of them is "active" at a time (ADR 003), also
persisted in `settings_store`. `vault_paths.get_master_vault()` is every
other vault module's entry point onto this — nothing outside this module
and `vault_paths.py` should read `VAULT_PATHS` or `settings_store`'s vault
keys directly.
"""

import os

from sympose import settings_store


def get_configured_vaults() -> list[dict[str, str]]:
    """Every configured vault — `VAULT_PATHS` (comma-separated) followed by
    any vault added at runtime via the workspace switcher (ADR 004) — as
    `{"name", "path"}`, env-declared vaults first, in declared/added order.
    `name` is the directory basename; when two configured vaults share a
    basename, both fall back to `<parent>/<basename>` so the switcher never
    shows two identical rows."""
    raw = os.getenv("VAULT_PATHS") or ""
    added = settings_store.get("added_vaults", [])
    paths = []
    seen = set()
    for part in [*raw.split(","), *added]:
        part = (part or "").strip()
        if not part:
            continue
        abspath = os.path.abspath(os.path.expanduser(part))
        if abspath not in seen:
            seen.add(abspath)
            paths.append(abspath)

    basenames = [os.path.basename(p) for p in paths]
    vaults = []
    for path, name in zip(paths, basenames):
        if basenames.count(name) > 1:
            name = os.path.join(os.path.basename(os.path.dirname(path)), name)
        vaults.append({"name": name, "path": path})
    return vaults


def add_vault(path: str) -> dict[str, str] | None:
    """Adds `path` to the persisted `added_vaults` list (ADR 004) — the
    workspace switcher's add-path input, for a vault outside `VAULT_PATHS`.
    Idempotent: a `path` that's already configured (env or previously added)
    just returns its existing entry rather than duplicating it. Rejects
    (`None`) a blank path, one that isn't an existing directory — this
    points at a real, already-created Obsidian vault, it doesn't create
    one — or one that couldn't actually be persisted (`settings_store.set`
    failing, e.g. a read-only settings directory)."""
    path = (path or "").strip()
    if not path:
        return None
    abspath = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(abspath):
        return None
    existing = next(
        (v for v in get_configured_vaults() if v["path"] == abspath), None
    )
    if existing:
        return existing
    added = settings_store.get("added_vaults", [])
    if not settings_store.set("added_vaults", [*added, abspath]):
        return None
    return next(
        (v for v in get_configured_vaults() if v["path"] == abspath), None
    )


def get_active_vault_path() -> str | None:
    """The currently active vault's path: the persisted `active_vault`
    setting when it still names a configured vault, else the first
    configured vault, else `None` when nothing is configured at all."""
    vaults = get_configured_vaults()
    if not vaults:
        return None
    saved = settings_store.get("active_vault")
    if saved and any(v["path"] == saved for v in vaults):
        return saved
    return vaults[0]["path"]


def set_active_vault(path: str) -> bool:
    """Persists `path` as the active vault. Rejects any path that isn't one
    of `get_configured_vaults()` — this is a selection among pre-configured
    vaults, not an arbitrary filesystem write."""
    abspath = os.path.abspath(os.path.expanduser(path))
    if not any(v["path"] == abspath for v in get_configured_vaults()):
        return False
    return settings_store.set("active_vault", abspath)
