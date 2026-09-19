"""
Writing/appending a note in the persona's own primary folder (ADR-136,
split out of vault_write.py): `write_note` (create-or-replace, template
seeded), `append_note` (falls back to `write_note` for a not-yet-existing
file). Both hold `compactor.get_file_lock(target_file)` across their
mtime-check-through-write span (ADR-129 same-process concurrency guard).
"""

import datetime
import os
from typing import Any, Callable

from sympose import vault_manifest, vault_paths
from sympose.compactor import get_file_lock
from sympose.config import is_safe_path
from sympose.vault_write_concurrency import NOTE_CONFLICT, mtime_matches
from sympose.vault_write_core import (
    _daily_notes_root,
    _render_template,
    _targets_daily_root,
    get_template_for_path,
)
from sympose.vault_write_status import _NOOP_HOOK


def write_note(
    profile: dict[str, Any],
    note_name: str,
    content: str,
    *,
    reindex_hook: Callable[[str, str], None] = _NOOP_HOOK,
    manifest_hook: Callable[[str, str], None] = _NOOP_HOOK,
    expected_mtime: float | None = None,
) -> str:
    mv, allowed_dirs, primary_dir = (
        vault_paths.get_master_vault(),
        vault_paths.get_allowed_dirs(profile),
        vault_paths.get_primary_dir(profile),
    )
    if not mv or not primary_dir:
        return "Warning: Master notes directory not configured or path denied."
    if not (note_name.endswith(".md") or note_name.endswith(".canvas")):
        note_name += ".md"
    target_file = (
        os.path.join(mv, note_name)
        if ("/" in note_name or "\\" in note_name)
        else os.path.join(primary_dir, note_name)
    )
    if not any(is_safe_path(target_file, allowed) for allowed in allowed_dirs):
        return f"Security Error: Target path `{note_name}` is outside assigned sandbox."
    if _targets_daily_root(target_file, mv):
        return (
            f"Warning: `{_daily_notes_root()}/` is reserved for daily entries — "
            "use [DAILY_NOTE] instead of writing directly into that folder."
        )
    with get_file_lock(target_file):
        if not mtime_matches(target_file, expected_mtime):
            return NOTE_CONFLICT
        return _write_note_locked(
            mv, target_file, note_name, content, reindex_hook, manifest_hook
        )


def _write_note_locked(
    mv: str,
    target_file: str,
    note_name: str,
    content: str,
    reindex_hook: Callable[[str, str], None],
    manifest_hook: Callable[[str, str], None],
) -> str:
    """The actual write behind `write_note` — caller must already hold
    `get_file_lock(target_file)`. Split out so `append_note`'s
    file-doesn't-exist fallback can reuse it without acquiring the same
    (non-reentrant) lock twice."""
    now = datetime.datetime.now().astimezone()
    date_str, time_str, rel_display = (
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M"),
        os.path.relpath(target_file, mv),
    )
    clean_content = content.strip()

    try:
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        # If model already provided YAML frontmatter, write clean content directly
        if clean_content.startswith("---"):
            final_content = clean_content + "\n"
        else:
            title_heading = (
                os.path.splitext(os.path.basename(note_name))[0]
                .replace("_", " ")
                .title()
            )
            raw_tmpl = get_template_for_path(mv, note_name)
            if raw_tmpl and raw_tmpl.strip().startswith("---"):
                rendered_tmpl = _render_template(raw_tmpl, title_heading, now)
                final_content = (
                    f"{rendered_tmpl}\n\n# {title_heading}\n\n{clean_content}\n"
                )
            else:
                final_content = (
                    f"---\n"
                    f"title: {title_heading}\n"
                    f"created: {date_str} {time_str}\n"
                    f"tags: []\n"
                    f"---\n\n"
                    f"# {title_heading}\n\n"
                    f"{clean_content}\n"
                )

        vault_manifest.write_atomic_text(target_file, final_content)
        reindex_hook(mv, target_file)
        manifest_hook(mv, target_file)
        return f"Saved to note: `{rel_display}`"
    except Exception as e:
        return f"Error: Failed to write note: {e}"


def append_note(
    profile: dict[str, Any],
    note_name: str,
    content: str,
    *,
    reindex_hook: Callable[[str, str], None] = _NOOP_HOOK,
    manifest_hook: Callable[[str, str], None] = _NOOP_HOOK,
    expected_mtime: float | None = None,
) -> str:
    mv, allowed_dirs, primary_dir = (
        vault_paths.get_master_vault(),
        vault_paths.get_allowed_dirs(profile),
        vault_paths.get_primary_dir(profile),
    )
    if not mv or not primary_dir:
        return "Warning: Master notes directory not configured or path denied."
    if not (note_name.endswith(".md") or note_name.endswith(".canvas")):
        note_name += ".md"
    target_file = (
        os.path.join(mv, note_name)
        if ("/" in note_name or "\\" in note_name)
        else os.path.join(primary_dir, note_name)
    )
    if not any(is_safe_path(target_file, allowed) for allowed in allowed_dirs):
        return f"Security Error: Target path `{note_name}` is outside assigned sandbox."
    with get_file_lock(target_file):
        if not mtime_matches(target_file, expected_mtime):
            return NOTE_CONFLICT

        rel_display = os.path.relpath(target_file, mv)
        try:
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            if not os.path.exists(target_file):
                return _write_note_locked(
                    mv, target_file, note_name, content, reindex_hook, manifest_hook
                )

            # errors="replace" matches vault_note_read.py's own reads, so a
            # stray non-UTF-8 byte in the untouched existing content can't
            # turn a pure append into a decode failure. newline="" disables
            # universal-newline translation, so existing CRLF line endings
            # in that untouched content pass through unmodified instead of
            # being silently normalized to LF on every append.
            with open(target_file, "r", encoding="utf-8", errors="replace", newline="") as f:
                existing = f.read()
            vault_manifest.write_atomic_text(
                target_file, f"{existing}\n{content.strip()}\n"
            )
            reindex_hook(mv, target_file)
            manifest_hook(mv, target_file)
            return f"Appended to note: `{rel_display}`"
        except Exception as e:
            return f"Error: Failed to append note: {e}"
