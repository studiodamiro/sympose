"""
Folder-level vault operations: the high-density digest and random-sample
ground-truth extraction used by a folder-scoped turn, plus the
`has_vault_skill` gate. Folder/skill *discovery* (real subfolders,
chronological/daily-journal notes) lives in vault_folder_discovery.py — a
second-pass split of this same ADR-125 cluster, composed in below via
`FoldersMixin(DiscoveryMixin)` so vault.py's own class declaration doesn't
need to change.

Split out of vault.py per ADR-125 purely to keep that file under this
project's own size guidance; every method here is unchanged from its
prior home, so `VaultManager(FoldersMixin, ...)` is a pure move, not a
rewrite. Depends on `cls._get_master_vault`, `cls.get_allowed_dirs`, and
`cls._get_vault_snapshot`, all resolved normally through the MRO once
`VaultManager` inherits from this mixin, no parameter threading needed.
"""

import logging
import os
import re
from typing import Any

from sympose.config import config_manager, is_safe_path
from sympose.vault_folder_discovery import DiscoveryMixin

log = logging.getLogger(__name__)


class FoldersMixin(DiscoveryMixin):
    @classmethod
    def get_folder_digest(
        cls, profile: dict[str, Any], folder_name: str, max_files: int = 50
    ) -> str:
        """Extracts high-density 1-line metadata for all notes in a folder for comprehensive synthesis."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return "⚠️ Master notes directory not configured or access denied."
        target_dir = cls._resolve_named_folder_dir(allowed_dirs, folder_name)
        if not target_dir or not os.path.exists(target_dir):
            return f"Folder `{folder_name}` not found in allowed vault directories."

        entries: list[str] = []
        for entry in cls._get_vault_snapshot(mv, [target_dir])[:max_files]:
            fn, head = entry["file_name"], entry["full_content"][:1000]
            parts = []
            for k in (
                "name",
                "title",
                "aka",
                "tags",
                "birthday",
                "created",
                "up",
                "author",
            ):
                m = re.search(
                    rf"^{k}:\s*([^\n\r]+)", head, re.MULTILINE | re.IGNORECASE
                )
                if (
                    m
                    and m.group(1).strip()
                    and not m.group(1).strip().startswith(("-", "["))
                ):
                    parts.append(f"{k.capitalize()}: {m.group(1).strip()}")
                else:
                    sub = re.findall(
                        rf"^{k}:(?:\s*\n)((?:\s+-\s+[^\n]+\n)+)",
                        head,
                        re.MULTILINE | re.IGNORECASE,
                    )
                    if sub:
                        items = [
                            x.strip("- \t\n\"'") for x in sub[0].strip().split("\n")
                        ]
                        parts.append(f"{k.capitalize()}: {', '.join(items)}")
            fl = next(
                (
                    line.strip("# \t\r")
                    for line in head.split("\n")
                    if line.strip() and not line.startswith("---") and ":" not in line
                ),
                "",
            )
            summary = " | ".join(parts) if parts else fl[:80]
            entries.append(f"- `{fn}`: {summary}" if summary else f"- `{fn}`")

        return (
            f"### High-Density Folder Digest (`{folder_name}/` - {len(entries)} notes):\n"
            + "\n".join(entries)
            if entries
            else f"No notes found in `{folder_name}/`."
        )

    @classmethod
    def get_random_sample_notes(
        cls, profile: dict[str, Any], folder_name: str, count: int = 2
    ) -> str:
        """Extracts real note bodies from 1-3 randomly sampled notes in the folder so the model has true ground-truth content."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return "⚠️ Master notes directory not configured or access denied."
        target_dir = cls._resolve_named_folder_dir(allowed_dirs, folder_name)
        if not target_dir or not os.path.exists(target_dir):
            return ""
        valid_files = cls._collect_sample_candidate_files(target_dir)
        if not valid_files:
            return ""
        return cls._sample_and_read_notes(mv, valid_files, count)

    @classmethod
    def _resolve_named_folder_dir(
        cls, allowed_dirs: list[str], folder_name: str
    ) -> str | None:
        """Resolves `folder_name` to a real directory: an allowed dir whose
        own basename matches, or an immediate subfolder of one."""
        target_dir = next(
            (
                d
                for d in allowed_dirs
                if os.path.basename(d).lower() == folder_name.lower()
            ),
            None,
        )
        if not target_dir:
            for d in allowed_dirs:
                candidate = os.path.join(d, folder_name)
                if os.path.exists(candidate) and is_safe_path(candidate, d):
                    target_dir = candidate
                    break
        return target_dir

    @classmethod
    def _collect_sample_candidate_files(cls, target_dir: str) -> list[str]:
        """Every note file under `target_dir`, respecting
        `vault.ignore_folders`."""
        raw_ignore = config_manager.get("vault.ignore_folders")
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        valid_files = []
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [
                d
                for d in dirs
                if d.lower() not in ignore_dirs and not d.startswith(".")
            ]
            for fn in files:
                if fn.endswith((".md", ".markdown", ".txt")):
                    valid_files.append(os.path.join(root, fn))
        return valid_files

    @classmethod
    def _sample_and_read_notes(
        cls, mv: str, valid_files: list[str], count: int
    ) -> str:
        """Randomly samples up to `count` files and reads their bodies as
        ground-truth payloads."""
        import random

        samples = random.sample(valid_files, min(count, len(valid_files)))
        payloads = []
        for fp in samples:
            rel = os.path.relpath(fp, mv)
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    body = f.read().strip()
                if body:
                    payloads.append(
                        f"### Ground-Truth Sandboxed Vault Note (`{rel}` - Exact Content):\n{body[:2500]}"
                    )
            except Exception as e:
                log.debug("Skipping sample note %s: %s", rel, e)
        return "\n\n---\n\n".join(payloads)

    @classmethod
    def has_vault_skill(cls, profile: dict[str, Any]) -> bool:
        """Verifies if the persona possesses the vault_read skill."""
        skills = profile.get("skills") or []
        return "vault_read" in skills

