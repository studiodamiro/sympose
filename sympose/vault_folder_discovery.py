"""
Folder/skill discovery: real subfolder names, and chronological/daily-
journal notes across allowed vault folders — each with the same manifest-
fast-path-or-direct-walk shape used elsewhere in this project.

Split out of vault_folders.py per ADR-125's own note that that cluster
("digest/sampling vs. discovery") would likely need a second pass once it
was out of vault.py and easier to judge on its own; every method here is
unchanged from its prior home. `FoldersMixin(DiscoveryMixin)` in
vault_folders.py composes this in, so vault.py's own
`class VaultManager(..., FoldersMixin, ...)` needs no change. Depends on
`cls._get_master_vault`, `cls.get_allowed_dirs`, and `cls.get_manifest`,
all resolved normally through the MRO.
"""

import logging
import os
import re
from typing import Any

from sympose.config import config_manager, is_safe_path

log = logging.getLogger(__name__)


class DiscoveryMixin:
    @staticmethod
    def _allowed_rel_prefixes(mv: str, allowed_dirs: list[str]) -> list[str]:
        """`allowed_dirs` as vault-relative "Foo/"-style prefixes; "" means the
        whole vault. For filtering the whole-vault manifest down to a persona's
        sandbox without touching disk."""
        out: list[str] = []
        mv_real = os.path.realpath(mv)
        for a in allowed_dirs:
            if os.path.realpath(a) == mv_real:
                return [""]
            out.append(os.path.relpath(a, mv).replace(os.sep, "/").rstrip("/") + "/")
        return out

    @classmethod
    def find_chronological_notes(cls, profile: dict[str, Any]) -> list[str]:
        """Dynamically discovers all chronological, daily, and journal notes
        across allowed vault folders: the manifest fast-path (ADR-078) when
        the map is live, a direct filesystem walk otherwise."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return []
        manifest = cls.get_manifest()
        if manifest is not None:
            return cls._chronological_notes_from_manifest(manifest, mv, allowed_dirs)
        return cls._chronological_notes_from_walk(allowed_dirs)

    @classmethod
    def _chronological_notes_from_manifest(
        cls, manifest: dict[str, Any], mv: str, allowed_dirs: list[str]
    ) -> list[str]:
        """Manifest fast-path (ADR-078) — no filesystem walk when the map is
        live."""
        date_re = re.compile(
            r"^\d{4}-\d{2}-\d{2}\.(?:md|markdown|txt)$", re.IGNORECASE
        )
        prefixes = cls._allowed_rel_prefixes(mv, allowed_dirs)
        hits: list[str] = []
        for n in manifest.get("nodes", []):
            rel = str(n.get("rel_path", "")).replace(os.sep, "/")
            if (
                not n.get("exists")
                or not rel.endswith((".md", ".markdown", ".txt"))
                or rel.endswith(".excalidraw.md")
            ):
                continue
            if not any(p == "" or rel.startswith(p) for p in prefixes):
                continue
            folder_low = os.path.dirname(rel).lower()
            if (
                date_re.match(os.path.basename(rel))
                or "daily" in folder_low
                or "journal" in folder_low
                or "diary" in folder_low
            ):
                hits.append(os.path.join(mv, n["rel_path"]))
        return hits

    @classmethod
    def _chronological_notes_from_walk(cls, allowed_dirs: list[str]) -> list[str]:
        """Direct filesystem walk, used when no manifest is available."""
        raw_ignore = config_manager.get("vault.ignore_folders")
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}\.(?:md|markdown|txt)$")

        results: list[str] = []
        for allowed in allowed_dirs:
            if not os.path.exists(allowed):
                continue
            for root, dirs, files in os.walk(allowed):
                dirs[:] = [
                    d
                    for d in dirs
                    if not d.startswith(".") and d.lower() not in ignore_dirs
                ]
                for fn in files:
                    if fn.endswith((".md", ".markdown", ".txt")) and not fn.endswith(
                        ".excalidraw.md"
                    ):
                        fp = os.path.join(root, fn)
                        if is_safe_path(fp, allowed):
                            if (
                                date_pattern.match(fn)
                                or "daily" in root.lower()
                                or "journal" in root.lower()
                                or "diary" in root.lower()
                            ):
                                results.append(fp)
        return results

    @classmethod
    def get_discovered_folders(cls, profile: dict[str, Any]) -> dict[str, str]:
        """Discovers real directory names and their full paths dynamically
        across allowed vault folders: the manifest fast-path (ADR-078) when
        the map is live, a direct scandir otherwise."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return {}
        manifest = cls.get_manifest()
        if manifest is not None:
            return cls._discovered_folders_from_manifest(manifest, mv, allowed_dirs)
        return cls._discovered_folders_from_scandir(mv, allowed_dirs)

    @classmethod
    def _discovered_folders_from_manifest(
        cls, manifest: dict[str, Any], mv: str, allowed_dirs: list[str]
    ) -> dict[str, str]:
        """Manifest fast-path (ADR-078) — immediate child folders of each
        allowed dir straight from the map's folder index, no scandir."""
        folder_keys = list(manifest.get("folders", {}).keys())
        discovered = {}
        mv_real = os.path.realpath(mv)
        for allowed in allowed_dirs:
            scoped = os.path.realpath(allowed) != mv_real
            prefix = (
                (os.path.relpath(allowed, mv).replace(os.sep, "/").rstrip("/") + "/")
                if scoped
                else ""
            )
            if scoped:
                discovered[os.path.basename(allowed).lower()] = allowed
            for key in folder_keys:
                k = key.replace(os.sep, "/")
                if prefix and not k.startswith(prefix):
                    continue
                rest = k[len(prefix) :]
                if rest and "/" not in rest:  # immediate child only
                    discovered[rest.lower()] = os.path.join(mv, key)
        return discovered

    @classmethod
    def _discovered_folders_from_scandir(
        cls, mv: str, allowed_dirs: list[str]
    ) -> dict[str, str]:
        """Direct scandir, used when no manifest is available."""
        raw_ignore = config_manager.get("vault.ignore_folders")
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        discovered: dict[str, str] = {}

        for allowed in allowed_dirs:
            if not os.path.exists(allowed):
                continue
            if allowed != mv:
                discovered[os.path.basename(allowed).lower()] = allowed
            try:
                for entry in os.scandir(allowed):
                    if (
                        entry.is_dir()
                        and not entry.name.startswith(".")
                        and entry.name.lower() not in ignore_dirs
                    ):
                        discovered[entry.name.lower()] = entry.path
            except Exception as e:
                log.debug("Failed to scan %s for sub-vaults: %s", allowed, e)
        return discovered
