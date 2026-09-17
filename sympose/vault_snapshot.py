"""
Vault content snapshot + the ADR-078 structural manifest glue — the
mtime-cached, flat read of every note under a set of directories that
`search_structured()`, `get_folder_digest()`, and the manifest builder all
share, plus the manifest's own on-demand build/refresh and incremental
per-write patch hooks.

Split out of vault.py per ADR-125 purely to keep that file under this
project's own size guidance; every method here is unchanged from its
prior home, so `VaultManager(SnapshotMixin, ...)` is a pure move, not a
rewrite. Depends on `cls.parse_frontmatter` and `cls._get_master_vault`,
both of which stay on `VaultManager` itself — resolved normally through
the MRO once `VaultManager` inherits from this mixin, no parameter
threading needed.
"""

import logging
import os
from typing import Any

from sympose import vault_index, vault_manifest, vault_paths
from sympose.config import config_manager, is_safe_path
from sympose.workspace import resolve_workspace_dir

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vault content snapshot cache — avoids re-walking + re-reading every note on
# every search_structured() / get_folder_digest() call. Same mtime-keyed
# invalidation strategy as vault_links' own backlink cache.
# Key: tuple of scanned dir paths → (combined_mtime, flat list of parsed notes)
# ---------------------------------------------------------------------------
_VAULT_SNAPSHOT_CACHE: dict[tuple[str, ...], tuple[float, list[dict[str, Any]]]] = {}


class SnapshotMixin:
    @classmethod
    def _get_vault_snapshot(cls, mv: str, dirs: list[str]) -> list[dict[str, Any]]:
        """Returns a cached, flat list of every note under `dirs` (path, parsed
        frontmatter, body, raw content), rebuilt only when a dir's mtime changes.
        Shared by search_structured() and get_folder_digest() so neither has to
        re-walk + re-read the vault from disk on every call."""
        raw_ignore = config_manager.get("vault.ignore_folders")
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        # Folded into the cache key (not just used to filter the walk) so an
        # ignore-list edit invalidates this cache on its own - a changed
        # ignore set doesn't reliably change any directory's own mtime (a
        # newly-unignored folder can easily be *older* than whatever else
        # last touched the vault), so relying on mtime drift alone silently
        # kept serving a snapshot built under the old list.
        cache_key = (tuple(sorted(dirs)), tuple(sorted(ignore_dirs)))
        current_mtime = vault_paths.dirs_mtime(dirs, ignore_dirs)
        cached_mtime, cached_snapshot = _VAULT_SNAPSHOT_CACHE.get(cache_key, (0.0, []))
        if current_mtime == cached_mtime and cached_snapshot:
            return cached_snapshot

        snapshot: list[dict[str, Any]] = []

        for allowed in dirs:
            if not os.path.exists(allowed):
                continue
            for root, subdirs, files in os.walk(allowed):
                subdirs[:] = [
                    d
                    for d in subdirs
                    if d.lower() not in ignore_dirs and not d.startswith(".")
                ]
                for file in sorted(files):
                    if not file.endswith((".md", ".markdown", ".txt")):
                        continue
                    file_path = os.path.join(root, file)
                    if not is_safe_path(file_path, allowed):
                        continue
                    try:
                        with open(
                            file_path, "r", encoding="utf-8", errors="replace"
                        ) as f:
                            full_content = f.read()
                    except Exception as e:
                        log.debug(
                            "Skipping unreadable file in snapshot %s: %s", file_path, e
                        )
                        continue
                    meta, body = cls.parse_frontmatter(full_content)
                    snapshot.append(
                        {
                            "file_name": file,
                            "rel_path": os.path.relpath(file_path, mv),
                            "abs_path": file_path,
                            "full_content": full_content,
                            "meta": meta,
                            "body": body,
                        }
                    )

        _VAULT_SNAPSHOT_CACHE[cache_key] = (current_mtime, snapshot)
        return snapshot

    @staticmethod
    def _workspace_dir() -> str:
        return resolve_workspace_dir()

    @classmethod
    def _reindex_note_if_enabled(cls, mv: str, target_file: str) -> None:
        """Best-effort incremental FTS reindex right after a Sympose-driven
        write, so the note is searchable on the very next query without
        waiting on the mtime-drift rebuild path (ADR-070.5). No-op — and
        costs nothing — unless `vault.search_mode: sqlite_fts` is active."""
        if config_manager.get("vault.search_mode", "direct") != "sqlite_fts":
            return
        try:
            with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                full_content = f.read()
            meta, body = cls.parse_frontmatter(full_content)
            vault_index.upsert_note(
                cls._workspace_dir(),
                mv,
                os.path.relpath(target_file, mv),
                os.path.basename(target_file),
                meta,
                body,
            )
        except Exception:
            log.debug(
                "[vault] incremental FTS reindex failed for %s",
                target_file,
                exc_info=True,
            )

    @classmethod
    def _update_manifest_if_enabled(cls, mv: str, target_file: str) -> None:
        """Best-effort single-node manifest patch right after a Sympose-driven
        write (ADR-078.5). No-op unless `vault.manifest.enabled` is set."""
        if not config_manager.get("vault.manifest.enabled"):
            return
        try:
            with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                full_content = f.read()
            meta, _ = cls.parse_frontmatter(full_content)
            vault_manifest.patch_note(
                cls._workspace_dir(),
                mv,
                os.path.relpath(target_file, mv),
                meta,
                full_content,
                ignore_folders=config_manager.get("vault.ignore_folders") or [],
            )
        except Exception:
            log.debug(
                "[vault] manifest patch failed for %s", target_file, exc_info=True
            )

    @classmethod
    def get_manifest(cls) -> dict[str, Any] | None:
        """The ADR-078 structural map (nodes, links, folders) for the whole
        vault, built/refreshed on demand. None when `vault.manifest.enabled` is
        off or no vault is set. Navigation only — never a grounding source;
        quoted content is still read from the note itself."""
        if not config_manager.get("vault.manifest.enabled"):
            return None
        mv = cls._get_master_vault()
        if not mv:
            return None
        return vault_manifest.ensure_fresh(
            cls._workspace_dir(),
            mv,
            lambda: cls._get_vault_snapshot(mv, [mv]),
            read_notes=lambda rels: cls._read_note_entries(mv, rels),
            ignore_folders=config_manager.get("vault.ignore_folders") or [],
            debounce=config_manager.get("vault.manifest.check_debounce_seconds"),
            max_nodes=config_manager.get("vault.manifest.max_nodes") or 0,
        )

    @classmethod
    def _read_note_entries(cls, mv: str, rel_paths: list[str]) -> list[dict[str, Any]]:
        """Read + parse just these notes into `_get_vault_snapshot`-shaped
        entries — the reader the ADR-078.4 manifest delta hands to
        `vault_manifest.ensure_fresh` so an external edit re-parses only what
        changed, not the whole vault."""
        out: list[dict[str, Any]] = []
        for rel in rel_paths:
            fp = os.path.join(mv, rel)
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    full_content = f.read()
            except OSError:
                continue
            meta, body = cls.parse_frontmatter(full_content)
            out.append(
                {
                    "file_name": os.path.basename(rel),
                    "rel_path": rel.replace(os.sep, "/"),
                    "abs_path": fp,
                    "full_content": full_content,
                    "meta": meta,
                    "body": body,
                }
            )
        return out
