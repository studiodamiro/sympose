"""
Shared low-level helpers (daily-root detection, workspace dir, Obsidian
template resolution) plus `overwrite_note` (ADR-136, split out of
vault_write.py). `write_note`/`append_note` live in `vault_write_note.py`
since they need `get_template_for_path`/`_render_template` from here.
"""

import datetime
import logging
import os
from typing import Any, Callable

from sympose import vault_manifest, vault_paths
from sympose.compactor import get_file_lock
from sympose.config import config_manager, is_safe_path
from sympose.vault_write_concurrency import NOTE_CONFLICT, mtime_matches
from sympose.vault_write_resolve import resolve_existing_note
from sympose.vault_write_status import NOTE_DENIED, NOTE_NOT_FOUND, _NOOP_HOOK

log = logging.getLogger(__name__)


def _daily_notes_root() -> str:
    """First path segment of the daily-notes format - workspace_rules.md
    tells personas this folder is off-limits for direct writes ("uses
    [DAILY_NOTE] system instead"), but that was prompt-text only with no
    code behind it until now: a model asked to write there directly just
    did (confirmed live). `write_daily_note` reads this exact env var to
    place real daily notes, so this is the same folder, not a guess."""
    fmt = os.getenv("DAILY_NOTES_FORMAT", "Daily/%Y/%m-%B/%Y-%m-%d.md")
    return fmt.split("/")[0].split("\\")[0]


def _targets_daily_root(target_file: str, mv: str) -> bool:
    """True when `target_file` would create a new entry directly under the
    daily-notes root, bypassing write_daily_note's format/tagging entirely."""
    daily_root = _daily_notes_root()
    if not daily_root:
        return False
    rel = os.path.relpath(target_file, mv).replace("\\", "/")
    return rel.split("/")[0] == daily_root


def _workspace_dir() -> str:
    return os.path.dirname(os.path.abspath(config_manager.config_path)) or "."


def get_template_for_path(mv: str, note_name: str) -> str | None:
    """Resolves the user's authentic Obsidian template from Templates/ folder if present.

    The folder->template match is derived from whichever templates actually
    live in Templates/ (its filename minus " template.md", matched against
    the note's top-level folder exactly or as a singular/plural pair) rather
    than a hardcoded list, so adding, renaming, or removing a template there
    takes effect with no code change. "Note template.md" is the fallback for
    any folder without a dedicated template.
    """
    tmpl_dir = os.path.join(mv, "Templates") if mv else ""
    if not mv or not os.path.isdir(tmpl_dir):
        return None

    norm = note_name.lower().replace("\\", "/")
    folder = norm.split("/", 1)[0] if "/" in norm else ""

    matched_file = None
    if folder:
        for fname in os.listdir(tmpl_dir):
            fname_lower = fname.lower()
            if fname_lower == "note template.md" or not fname_lower.endswith(
                "template.md"
            ):
                continue
            note_type = fname_lower[: -len("template.md")].strip()
            if folder in (note_type, note_type.rstrip("s"), note_type + "s"):
                matched_file = os.path.join(tmpl_dir, fname)
                break

    if not matched_file or not os.path.exists(matched_file):
        matched_file = os.path.join(tmpl_dir, "Note template.md")

    if os.path.exists(matched_file):
        try:
            with open(matched_file, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            log.debug("Failed to read template %s: %s", matched_file, e)
    return None


def _render_template(
    raw_tmpl: str, title_heading: str, now: "datetime.datetime"
) -> str:
    """Substitutes the core-Obsidian-Templates placeholders this vault's
    templates use: `{{date}}`, `{{time}}`, `{{title}}`, `{{date:YYYY}}`."""
    return (
        raw_tmpl.replace("{{date}}", now.strftime("%Y-%m-%d"))
        .replace("{{time}}", now.strftime("%H:%M"))
        .replace("{{title}}", title_heading)
        .replace("{{date:YYYY}}", now.strftime("%Y"))
    ).strip()


def overwrite_note(
    profile: dict[str, Any],
    note_name: str,
    content: str,
    *,
    reindex_hook: Callable[[str, str], None] = _NOOP_HOOK,
    manifest_hook: Callable[[str, str], None] = _NOOP_HOOK,
    expected_mtime: float | None = None,
) -> str:
    """Replace an *existing* vault note's file with `content`, verbatim (the
    editor already owns the whole document, frontmatter included). Resolves
    the same file `read_note` would return, so a dashboard save lands back on
    the note it was opened from. Overwrite only — a path with no existing
    file returns `NOTE_NOT_FOUND` rather than creating one (ADR-081); a path
    outside the persona's sandbox returns `NOTE_DENIED`. On success the note
    is re-indexed and the manifest refreshed, exactly as `write_note` does.
    """
    mv, allowed_dirs = (
        vault_paths.get_master_vault(),
        vault_paths.get_allowed_dirs(profile),
    )
    if not mv or not allowed_dirs:
        return NOTE_DENIED

    target_file = resolve_existing_note(profile, note_name)
    if target_file is None:
        return NOTE_NOT_FOUND
    if not any(is_safe_path(target_file, allowed) for allowed in allowed_dirs):
        return NOTE_DENIED
    with get_file_lock(target_file):
        if not mtime_matches(target_file, expected_mtime):
            return NOTE_CONFLICT

        rel_display = os.path.relpath(target_file, mv)
        try:
            vault_manifest.write_atomic_text(target_file, content.rstrip("\n") + "\n")
            reindex_hook(mv, target_file)
            manifest_hook(mv, target_file)
            return f"Saved note: `{rel_display}`"
        except Exception as e:
            return f"Error: Failed to write note: {e}"
