"""
Creating a brand-new note or empty folder — refuses rather than overwrites;
that's `vault_write.overwrite_note`'s job.
"""

import datetime
import os
from typing import Any

from sympose import vault_paths
from sympose.security import is_safe_path
from sympose.vault_write import get_file_lock, write_atomic_text
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS


def get_template_for_path(mv: str, note_name: str) -> str | None:
    """Resolves the user's own Obsidian template from `Templates/` if
    present. The folder->template match is derived from whichever
    templates actually live in `Templates/` (its filename minus " template.md",
    matched against the note's top-level folder exactly or as a
    singular/plural pair) rather than a hardcoded list. "Note template.md"
    is the fallback for any folder without a dedicated template."""
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
        except OSError:
            return None
    return None


def _render_template(raw_tmpl: str, title_heading: str, now: datetime.datetime) -> str:
    """Substitutes the core-Obsidian-Templates placeholders this vault's
    templates use: `{{date}}`, `{{time}}`, `{{title}}`, `{{date:YYYY}}`."""
    return (
        raw_tmpl.replace("{{date}}", now.strftime("%Y-%m-%d"))
        .replace("{{time}}", now.strftime("%H:%M"))
        .replace("{{title}}", title_heading)
        .replace("{{date:YYYY}}", now.strftime("%Y"))
    ).strip()


def create_note(
    profile: dict[str, Any], note_name: str, content: str | None = None
) -> str:
    """Create a *new* vault note. `note_name` is a path relative to the
    vault — `Folder/Sub/Title` — and is placed under the master vault when
    it contains a separator, otherwise in the persona's primary folder.
    Refuses (`NOTE_EXISTS`) rather than overwriting an existing file —
    that's `overwrite_note`'s job. `NOTE_DENIED` for a path outside the
    sandbox. When `content` is omitted, the folder's real Obsidian template
    is seeded so the editor opens onto the same frontmatter a hand-created
    note in that folder would get; a folder without a dedicated template
    falls back to a minimal title stub."""
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
    target_file = os.path.normpath(os.path.join(base, clean_name))
    if not any(is_safe_path(target_file, allowed) for allowed in allowed_dirs):
        return NOTE_DENIED

    with get_file_lock(target_file):
        if os.path.exists(target_file):
            return NOTE_EXISTS

        if content is None:
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
            write_atomic_text(
                target_file, content if content.endswith("\n") else content + "\n"
            )
            return f"Created note: `{rel_display}`"
        except OSError as e:
            return f"Error: Failed to create note: {e}"


def create_folder(profile: dict[str, Any], folder_name: str) -> str:
    """Create a new *empty* folder under the vault, alongside `create_note`'s
    path resolution and sandbox rules: `folder_name` is relative to the
    vault and lands under the master vault when it contains a separator,
    otherwise in the persona's primary folder. `NOTE_EXISTS` when the path
    is already a file or directory, `NOTE_DENIED` outside the sandbox."""
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

    rel_display = os.path.relpath(target_dir, mv)
    with get_file_lock(target_dir):
        if os.path.exists(target_dir):
            return NOTE_EXISTS
        try:
            os.makedirs(target_dir)
            return f"Created folder: `{rel_display}`"
        except FileExistsError:
            return NOTE_EXISTS
        except OSError as e:
            return f"Error: Failed to create folder: {e}"
