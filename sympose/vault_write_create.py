"""
Creating a brand-new note or empty folder (ADR-136, split out of
vault_write.py) — refuses rather than overwrites; that's `overwrite_note`'s
job (vault_write_core.py).
"""

import datetime
import os
from typing import Any, Callable

from sympose import vault_manifest, vault_paths
from sympose.compactor import get_file_lock
from sympose.config import is_safe_path
from sympose.vault_write_core import (
    _render_template,
    _targets_daily_root,
    get_template_for_path,
)
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS, _NOOP_HOOK


def create_note(
    profile: dict[str, Any],
    note_name: str,
    content: str | None = None,
    *,
    reindex_hook: Callable[[str, str], None] = _NOOP_HOOK,
    manifest_hook: Callable[[str, str], None] = _NOOP_HOOK,
) -> str:
    """Create a *new* vault note from the dashboard (ADR-083). `note_name` is
    a path relative to the vault — `Folder/Sub/Title` — and is placed under
    the master vault when it contains a separator, otherwise in the persona's
    primary folder. Refuses (`NOTE_EXISTS`) rather than overwriting an
    existing file — that is `overwrite_note`'s job. `NOTE_DENIED` for a path
    outside the sandbox. When `content` is omitted, the folder's real
    Obsidian template (ADR-113) is seeded so the editor opens onto the same
    frontmatter a hand-created note in that folder would get; a folder
    without a dedicated template falls back to a minimal title stub.
    Re-indexed and added to the manifest like any other write."""
    mv, allowed_dirs, primary_dir = (
        vault_paths.get_master_vault(),
        vault_paths.get_allowed_dirs(profile),
        vault_paths.get_primary_dir(profile),
    )
    if not mv or not allowed_dirs:
        return NOTE_DENIED
    clean_name = note_name.strip().strip("\"'").lstrip("/\\")
    if not clean_name:
        return NOTE_DENIED
    if not clean_name.endswith(".md"):
        clean_name += ".md"

    base = mv if ("/" in clean_name or "\\" in clean_name) else (primary_dir or mv)
    # `is_safe_path` resolves symlinks itself; keep `target_file` a plain
    # join so `os.path.relpath(…, mv)` here and in the re-index helpers
    # stays correct even when `mv` sits under a symlink (macOS `/var`).
    target_file = os.path.normpath(os.path.join(base, clean_name))
    if not any(is_safe_path(target_file, allowed) for allowed in allowed_dirs):
        return NOTE_DENIED
    if _targets_daily_root(target_file, mv):
        return NOTE_DENIED

    with get_file_lock(target_file):
        if os.path.exists(target_file):
            return NOTE_EXISTS

        if content is None or not content.strip():
            title = (
                os.path.splitext(os.path.basename(clean_name))[0]
                .replace("_", " ")
                .replace("-", " ")
                .strip()
                .title()
            )
            now = datetime.datetime.now().astimezone()
            raw_tmpl = get_template_for_path(mv, clean_name)
            if raw_tmpl and raw_tmpl.strip().startswith("---"):
                content = f"{_render_template(raw_tmpl, title, now)}\n\n# {title}\n\n"
            else:
                content = f"---\ntitle: {title}\ncreated: {now.strftime('%Y-%m-%d')}\ntags: []\n---\n\n# {title}\n\n"

        rel_display = os.path.relpath(target_file, mv)
        try:
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            vault_manifest.write_atomic_text(
                target_file, content if content.endswith("\n") else content + "\n"
            )
            reindex_hook(mv, target_file)
            manifest_hook(mv, target_file)
            return f"Created note: `{rel_display}`"
        except Exception as e:
            return f"Error: Failed to create note: {e}"


def create_folder(profile: dict[str, Any], folder_name: str) -> str:
    """Create a new *empty* folder under the vault (ADR-095), alongside
    `create_note`'s path resolution and sandbox rules: `folder_name` is
    relative to the vault and lands under the master vault when it
    contains a separator, otherwise in the persona's primary folder.
    `NOTE_EXISTS` when the path is already a file or directory,
    `NOTE_DENIED` outside the sandbox."""
    mv, allowed_dirs, primary_dir = (
        vault_paths.get_master_vault(),
        vault_paths.get_allowed_dirs(profile),
        vault_paths.get_primary_dir(profile),
    )
    if not mv or not allowed_dirs:
        return NOTE_DENIED
    clean_name = folder_name.strip().strip("\"'").strip("/\\")
    if not clean_name:
        return NOTE_DENIED

    base = mv if ("/" in clean_name or "\\" in clean_name) else (primary_dir or mv)
    target_dir = os.path.normpath(os.path.join(base, clean_name))
    if not any(is_safe_path(target_dir, allowed) for allowed in allowed_dirs):
        return NOTE_DENIED
    if os.path.exists(target_dir):
        return NOTE_EXISTS

    rel_display = os.path.relpath(target_dir, mv)
    try:
        os.makedirs(target_dir)
        return f"Created folder: `{rel_display}`"
    except Exception as e:
        return f"Error: Failed to create folder: {e}"
