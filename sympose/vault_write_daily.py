"""
Daily reflections and end-of-session logs (ADR-136, split out of
vault_write.py) — built on top of `append_note`, plus the frontmatter-tag
sync helper `write_daily_note` uses to keep a daily note's tags current.
"""

import datetime
import logging
import os
import re
from typing import Any, Callable

from sympose import vault_paths
from sympose.vault_write_note import append_note
from sympose.vault_write_status import _NOOP_HOOK

log = logging.getLogger(__name__)


def sync_frontmatter_tags(file_path: str, new_tags: list[str]) -> None:
    """Dynamically merges new tags into the file's YAML frontmatter block."""
    if not os.path.exists(file_path) or not new_tags:
        return
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            doc = f.read()

        m = re.match(r"^---\s*\n([\s\S]*?)\n---\s*\n", doc)
        if not m:
            return
        fm_body = m.group(1)

        existing_tags = []
        m_tags = re.search(r"tags:\s*\n((?:\s*-\s*[^\n]+\n*)*)", fm_body)
        m_inline = re.search(r"tags:\s*\[(.*?)\]", fm_body)

        if m_tags:
            existing_tags = [
                re.sub(r"^\s*-\s*", "", line).strip()
                for line in m_tags.group(1).splitlines()
                if line.strip()
            ]
        elif m_inline:
            existing_tags = [
                t.strip().strip("\"'")
                for t in m_inline.group(1).split(",")
                if t.strip()
            ]

        merged = list(dict.fromkeys(existing_tags + [t.lower() for t in new_tags if t]))
        tags_yaml = "tags:\n" + "\n".join([f"  - {t}" for t in merged])

        if m_tags:
            new_fm = fm_body[: m_tags.start()] + tags_yaml + fm_body[m_tags.end() :]
        elif m_inline:
            new_fm = re.sub(r"tags:\s*\[.*?\]", tags_yaml, fm_body)
        elif "tags:" in fm_body:
            new_fm = re.sub(r"tags:.*", tags_yaml, fm_body)
        else:
            new_fm = fm_body.strip() + "\n" + tags_yaml

        updated_doc = f"---\n{new_fm.strip()}\n---\n" + doc[m.end() :]
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated_doc)
    except Exception as e:
        log.debug("Frontmatter tag sync failed for %s: %s", file_path, e)


def write_daily_note(
    profile: dict[str, Any],
    reflection: str,
    *,
    reindex_hook: Callable[[str, str], None] = _NOOP_HOOK,
    manifest_hook: Callable[[str, str], None] = _NOOP_HOOK,
) -> str:
    now = datetime.datetime.now().astimezone()
    daily_fmt = os.getenv("DAILY_NOTES_FORMAT", "Daily/%Y/%m-%B/%Y-%m-%d.md")
    clean_ref = reflection.strip()

    # Extract tags from reflection
    found_tags = list(dict.fromkeys(re.findall(r"#([a-zA-Z0-9_\-]+)", clean_ref)))
    if not found_tags:
        found_tags = ["jour", "reflection"]
    elif "jour" not in [t.lower() for t in found_tags]:
        found_tags.insert(0, "jour")

    # Guarantee that daily entries always possess Obsidian tags footer
    if not re.search(r"(?:tags:|\b#jour\b)", clean_ref, re.IGNORECASE):
        clean_ref = f"{clean_ref}\n\nTags: " + " ".join(f"#{t}" for t in found_tags)

    note_rel_path = now.strftime(daily_fmt)
    res = append_note(
        profile,
        note_rel_path,
        f"\n### Reflection ({now.strftime('%H:%M')})\n{clean_ref}",
        reindex_hook=reindex_hook,
        manifest_hook=manifest_hook,
    )

    # Sync frontmatter tags at top of the file
    mv = vault_paths.get_master_vault()
    if mv:
        target_file = os.path.join(mv, note_rel_path)
        sync_frontmatter_tags(target_file, found_tags)

    return res


def write_session_note(
    profile: dict[str, Any],
    summary_md: str,
    subfolder: str = "Sessions",
    session_title: str | None = None,
) -> str:
    primary_dir, mv = (
        vault_paths.get_primary_dir(profile),
        vault_paths.get_master_vault(),
    )
    if not primary_dir or not mv:
        return "Warning: Master notes directory not configured or path denied."
    now, handle = (
        datetime.datetime.now().astimezone(),
        profile.get("handle", "persona").lower(),
    )
    title_slug = f"_{session_title.lower().replace(' ', '_')}" if session_title else ""
    target_dir = os.path.join(primary_dir, subfolder)
    target_file = os.path.join(
        target_dir,
        f"{now.strftime('%Y-%m-%d_%H%M')}_{handle}{title_slug}_session.md",
    )
    try:
        os.makedirs(target_dir, exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(
                f"---\nentry: {now.strftime('%Y-%m-%d')}\ncreated: {now.strftime('%Y-%m-%d %H:%M')}\ntype: session-log\nproject: sympose\nauthor: {profile.get('name', handle)}\ntags:\n  - session/log\n  - sympose/{handle}\n---\n\n# Session Log: {profile.get('name', handle)} ({now.strftime('%Y-%m-%d %H:%M')})\n\n{summary_md.strip()}\n"
            )
        return f"Saved session note to Obsidian: `{os.path.relpath(target_file, mv)}`"
    except Exception as e:
        return f"Error: Failed to write session note: {e}"
