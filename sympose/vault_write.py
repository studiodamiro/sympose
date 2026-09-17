"""
Vault note/folder mutation: templates, create/write/append/overwrite,
rename (with wikilink retargeting), delete (to `.trash`), and the
daily/session-note writers built on top of them.

Every function here does the filesystem mechanics and sandbox checks only —
re-indexing, manifest patching, and backlink-cache invalidation are the
caller's job, taken as optional hook parameters (`reindex_hook`,
`manifest_hook`, `on_backlinks_changed`) rather than imported directly. That
keeps this module free of any dependency on `sympose.vault` itself (which
already depends on this module — importing back would cycle), and matches
`vault_trash.py`'s existing pattern of "thin wrappers in vault.py own the
side effects, the satellite module owns the mechanics."
"""

import datetime
import logging
import os
import re
from typing import Any, Callable

from sympose import vault_index, vault_manifest, vault_paths, vault_trash
from sympose.config import config_manager, is_safe_path

log = logging.getLogger(__name__)


def _daily_notes_root() -> str:
    """First path segment of the daily-notes format - workspace_rules.md
    tells personas this folder is off-limits for direct writes ("uses
    [DAILY_NOTE] system instead"), but that was prompt-text only with no
    code behind it until now: a model asked to write there directly just
    did (confirmed live). `write_daily_note` below reads this exact env var
    to place real daily notes, so this is the same folder, not a guess."""
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

# Sentinels — mapped onto VaultManager.NOTE_* (same values) so the server
# sees one consistent status vocabulary regardless of which module a result
# actually came from.
NOTE_NOT_FOUND = "__note_not_found__"
NOTE_DENIED = "__note_denied__"
NOTE_EXISTS = "__note_exists__"

_NOOP_HOOK: Callable[[str, str], None] = lambda mv, path: None  # noqa: E731
_NOOP_CALLBACK: Callable[[], None] = lambda: None  # noqa: E731

_WIKILINK_RE = re.compile(r"(!?)\[\[([^\[\]\r\n]+?)\]\]")


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


def write_note(
    profile: dict[str, Any],
    note_name: str,
    content: str,
    *,
    reindex_hook: Callable[[str, str], None] = _NOOP_HOOK,
    manifest_hook: Callable[[str, str], None] = _NOOP_HOOK,
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

    rel_display = os.path.relpath(target_file, mv)
    try:
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        if not os.path.exists(target_file):
            return write_note(
                profile,
                note_name,
                content,
                reindex_hook=reindex_hook,
                manifest_hook=manifest_hook,
            )

        with open(target_file, "a", encoding="utf-8") as f:
            f.write(f"\n{content.strip()}\n")
        reindex_hook(mv, target_file)
        manifest_hook(mv, target_file)
        return f"Appended to note: `{rel_display}`"
    except Exception as e:
        return f"Error: Failed to append note: {e}"


def _resolve_note_direct(mv: str, allowed_dirs: list[str], clean: str) -> str | None:
    """Case 1 — a direct path under the master vault."""
    direct = os.path.join(mv, clean)
    for allowed in allowed_dirs:
        if is_safe_path(direct, allowed) and os.path.isfile(direct):
            return direct
    return None


def _resolve_note_by_basename(allowed_dirs: list[str], clean: str) -> str | None:
    """Case 2 — the bare filename at an allowed dir's own top level."""
    for allowed in allowed_dirs:
        cand = os.path.join(allowed, os.path.basename(clean))
        if is_safe_path(cand, allowed) and os.path.isfile(cand):
            return cand
    return None


def _resolve_note_recursively(allowed_dirs: list[str], stem: str) -> str | None:
    """Case 3 — a recursive case-insensitive stem match anywhere under an
    allowed dir."""
    raw_ignore = config_manager.get("vault.ignore_folders")
    ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
    for allowed in allowed_dirs:
        for root, dirs, files in os.walk(allowed):
            dirs[:] = [
                d
                for d in dirs
                if d.lower() not in ignore_dirs and not d.startswith(".")
            ]
            for fn in files:
                if fn.endswith(".md") and os.path.splitext(fn)[0].lower() == stem:
                    fp = os.path.join(root, fn)
                    if is_safe_path(fp, allowed):
                        return fp
    return None


def resolve_existing_note(profile: dict[str, Any], note_name: str) -> str | None:
    """Absolute path of the file `VaultManager.read_note` would open for
    `note_name`, or `None`: direct path under the master vault → basename in
    an allowed folder → recursive case-insensitive stem match. Shared by
    `overwrite_note` / `rename_note` / `delete_note`."""
    mv, allowed_dirs = (
        vault_paths.get_master_vault(),
        vault_paths.get_allowed_dirs(profile),
    )
    if not mv or not allowed_dirs:
        return None
    clean = note_name.strip().strip("\"'")
    if not clean.endswith(".md"):
        clean += ".md"

    stem = os.path.splitext(os.path.basename(clean))[0].lower()
    return (
        _resolve_note_direct(mv, allowed_dirs, clean)
        or _resolve_note_by_basename(allowed_dirs, clean)
        or _resolve_note_recursively(allowed_dirs, stem)
    )


def overwrite_note(
    profile: dict[str, Any],
    note_name: str,
    content: str,
    *,
    reindex_hook: Callable[[str, str], None] = _NOOP_HOOK,
    manifest_hook: Callable[[str, str], None] = _NOOP_HOOK,
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

    rel_display = os.path.relpath(target_file, mv)
    try:
        vault_manifest.write_atomic_text(target_file, content.rstrip("\n") + "\n")
        reindex_hook(mv, target_file)
        manifest_hook(mv, target_file)
        return f"Saved note: `{rel_display}`"
    except Exception as e:
        return f"Error: Failed to write note: {e}"


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


def _trash_nonempty_folder(
    mv: str, target_dir: str, clean_name: str
) -> tuple[str | None, str | None]:
    """Moves a non-empty folder to `<vault>/.trash/<name>` (appending a
    timestamp if that name is already taken). Returns (dest, None) on
    success, or (None, error-or-NOTE_DENIED)."""
    dest = os.path.join(mv, vault_trash.TRASH_DIRNAME, clean_name)
    if not is_safe_path(dest, mv):
        return None, NOTE_DENIED
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            dest = f"{dest}-{datetime.datetime.now().astimezone().strftime('%Y%m%d%H%M%S')}"
        os.rename(target_dir, dest)
    except OSError as e:
        return None, f"Error: Failed to delete folder: {e}"
    return dest, None


def _deindex_moved_folder_notes(ws: str, mv: str, dest: str, clean_name: str) -> int:
    """De-indexes every note under a folder just moved to the trash.
    Returns how many notes were processed."""
    ignore = config_manager.get("vault.ignore_folders") or []
    note_count = 0
    for root, _, files in os.walk(dest):
        for fn in files:
            if not fn.endswith((".md", ".markdown", ".txt")):
                continue
            sub_rel = os.path.relpath(os.path.join(root, fn), dest)
            orig_rel = os.path.join(clean_name, sub_rel)
            try:
                vault_index.remove_note(ws, mv, orig_rel)
                vault_manifest.remove_note(ws, mv, orig_rel, ignore_folders=ignore)
            except Exception:
                log.debug(
                    "[vault] folder-delete de-index failed for %s",
                    orig_rel,
                    exc_info=True,
                )
            note_count += 1
    return note_count


def delete_folder(
    profile: dict[str, Any],
    folder_name: str,
    *,
    on_backlinks_changed: Callable[[], None] = _NOOP_CALLBACK,
) -> str:
    """Delete a vault folder (ADR-099). An *empty* folder is removed
    outright (`os.rmdir`) — nothing to recover. A folder holding notes
    and/or subfolders moves as one unit to `<vault>/.trash/`, the same
    `os.rename` `delete_note` uses, then every note inside is de-indexed
    individually — the whole subtree drops out of search/the graph while
    it sits in the bin. `vault_trash`'s list/restore/purge need no changes
    for this: each moved note is just another independently recoverable
    row there, and restoring one recreates its parent folder on the way
    back. `NOTE_NOT_FOUND` when the path isn't a real folder, `NOTE_DENIED`
    outside the sandbox."""
    mv, allowed_dirs = (
        vault_paths.get_master_vault(),
        vault_paths.get_allowed_dirs(profile),
    )
    if not mv or not allowed_dirs:
        return NOTE_DENIED
    clean_name = folder_name.strip().strip("\"'").strip("/\\")
    if not clean_name:
        return NOTE_DENIED
    target_dir = os.path.normpath(os.path.join(mv, clean_name))
    if not any(is_safe_path(target_dir, allowed) for allowed in allowed_dirs):
        return NOTE_DENIED
    if not os.path.isdir(target_dir):
        return NOTE_NOT_FOUND

    rel_display = os.path.relpath(target_dir, mv)
    if not os.listdir(target_dir):
        try:
            os.rmdir(target_dir)
            return f"Deleted empty folder: `{rel_display}`"
        except OSError as e:
            return f"Error: Failed to delete folder: {e}"

    dest, error = _trash_nonempty_folder(mv, target_dir, clean_name)
    if error is not None:
        return error

    ws = _workspace_dir()
    note_count = _deindex_moved_folder_notes(ws, mv, dest, clean_name)
    on_backlinks_changed()
    plural = "s" if note_count != 1 else ""
    dest_rel = os.path.relpath(dest, mv).replace(os.sep, "/")
    return f"Moved folder to the bin: `{dest_rel}` ({note_count} note{plural})"


def rewrite_wikilink_targets(
    text: str,
    old_rel_path: str,
    new_stem: str,
    source_rel_path: str,
    same_stem_paths: set[str],
) -> tuple[str, int]:
    """Retarget every `[[old]]` / `![[old]]` / `[[old#h]]` / `[[old|a]]`
    (and the `Folder/old` path form) that actually refers to the note being
    renamed, leaving any `#heading` and `|alias` intact. Returns the
    rewritten text and the hit count.

    D3: a bare `[[old_stem]]` used to be rewritten on filename match alone,
    regardless of which folder it lived in — retargeting a link that
    genuinely meant a *different*, same-named note elsewhere. `same_stem_paths`
    is every other real vault-relative path sharing the renamed note's stem;
    when that set is non-empty, a bare link (no folder in its own text) is
    only rewritten when this occurrence's own file (`source_rel_path`) sits
    in the renamed note's own top-level folder — Obsidian's own preference
    for resolving an unqualified link — otherwise it's left alone rather
    than guessed at. A link that's already folder-qualified in its own text
    (`[[Folder/old]]`) is unaffected by that ambiguity: it's only rewritten
    when its own qualifying segments actually match the renamed note's own
    path, not just its bare filename."""
    old_stem = os.path.splitext(os.path.basename(old_rel_path))[0]
    old_l = old_stem.strip().lower()
    old_segs_l = [s.lower() for s in old_rel_path.replace("\\", "/").split("/")[:-1]]
    old_top = old_segs_l[0] if old_segs_l else ""
    source_segs = source_rel_path.replace("\\", "/").split("/")[:-1]
    source_top = source_segs[0].lower() if source_segs else ""
    bare_is_safe = not same_stem_paths or source_top == old_top
    rewritten = 0

    def repl(m: "re.Match[str]") -> str:
        nonlocal rewritten
        bang, inner = m.group(1), m.group(2)
        head = re.match(r"^([^#|]*)(.*)$", inner)
        target, tail = head.group(1), head.group(2)
        segs = target.split("/")
        if segs[-1].strip().lower() != old_l:
            return m.group(0)
        if len(segs) == 1:
            if not bare_is_safe:
                return m.group(0)
        else:
            qualifier = [s.lower() for s in segs[:-1]]
            if qualifier != old_segs_l[-len(qualifier) :]:
                return m.group(0)
        rewritten += 1
        segs[-1] = new_stem
        return f"{bang}[[{'/'.join(segs)}{tail}]]"

    new_text = _WIKILINK_RE.sub(repl, text)
    return new_text, rewritten


def _resolve_rename_destination(
    mv: str, allowed_dirs: list[str], src: str, new_name: str
) -> tuple[str | None, str]:
    """Validates and resolves `new_name`'s destination path for a rename:
    same folder as `src` unless `new_name` itself carries a separator.
    Returns (dst, "") on success, or (None, NOTE_DENIED|NOTE_EXISTS)."""
    clean_new = new_name.strip().strip("\"'").lstrip("/\\")
    if not clean_new:
        return None, NOTE_DENIED
    if not clean_new.endswith(".md"):
        clean_new += ".md"
    # Plain join (not realpath) so the relpaths below stay correct under a
    # symlinked vault root; `is_safe_path` resolves symlinks on its own.
    dst = os.path.normpath(
        os.path.join(mv, clean_new)
        if ("/" in clean_new or "\\" in clean_new)
        else os.path.join(os.path.dirname(src), clean_new)
    )
    if not any(is_safe_path(dst, allowed) for allowed in allowed_dirs):
        return None, NOTE_DENIED
    if os.path.exists(dst):
        return None, NOTE_EXISTS
    return dst, ""


def _relink_one_referencing_file(
    mv: str,
    allowed_dirs: list[str],
    fp: str,
    source_rel: str,
    old_rel: str,
    new_stem: str,
    same_stem_paths: set[str],
    reindex_hook: Callable[[str, str], None],
    manifest_hook: Callable[[str, str], None],
) -> bool:
    """Rewrites one referencing file's wikilinks in place if it's a real,
    in-sandbox file with an actual hit. Returns whether it was updated."""
    if not os.path.isfile(fp) or not any(
        is_safe_path(fp, allowed) for allowed in allowed_dirs
    ):
        return False
    try:
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        rewritten, hits = rewrite_wikilink_targets(
            content, old_rel, new_stem, source_rel, same_stem_paths
        )
        if not hits:
            return False
        with open(fp, "w", encoding="utf-8") as f:
            f.write(rewritten)
        reindex_hook(mv, fp)
        manifest_hook(mv, fp)
        return True
    except OSError:
        return False


def _relink_referencing_notes(
    mv: str,
    allowed_dirs: list[str],
    ref_files: list[str],
    old_rel: str,
    new_rel: str,
    dst: str,
    new_stem: str,
    same_stem_paths: set[str],
    reindex_hook: Callable[[str, str], None],
    manifest_hook: Callable[[str, str], None],
) -> int:
    updated = 0
    for rel in ref_files:
        # The renamed note's own self-referencing wikilinks live at its
        # *new* path now — `fp` would point at `src`, which no longer
        # exists post-rename.
        fp = dst if rel == old_rel else os.path.join(mv, rel)
        source_rel = new_rel if rel == old_rel else rel
        if _relink_one_referencing_file(
            mv,
            allowed_dirs,
            fp,
            source_rel,
            old_rel,
            new_stem,
            same_stem_paths,
            reindex_hook,
            manifest_hook,
        ):
            updated += 1
    return updated


def rename_note(
    profile: dict[str, Any],
    old_name: str,
    new_name: str,
    *,
    get_backlinks_fn: Callable[[dict[str, Any], str], list[dict[str, Any]]],
    find_notes_by_stem_fn: Callable[[dict[str, Any], str], list[str]] = (
        lambda profile, stem: []
    ),
    reindex_hook: Callable[[str, str], None] = _NOOP_HOOK,
    manifest_hook: Callable[[str, str], None] = _NOOP_HOOK,
    on_backlinks_changed: Callable[[], None] = _NOOP_CALLBACK,
) -> str:
    """Rename a vault note and rewrite every `[[wikilink]]` that pointed at
    it (ADR-084). `new_name` stays in the same folder unless it carries a
    separator. `NOTE_NOT_FOUND` / `NOTE_EXISTS` / `NOTE_DENIED` as for the
    other note ops. `get_backlinks_fn` finds the referencing notes — vault.py
    passes `VaultManager.get_backlinks` (that logic hasn't moved out of
    vault.py yet). `find_notes_by_stem_fn` (D3) finds every other real note
    sharing the renamed note's stem, so a bare wikilink's rewrite can tell
    an unambiguous case from one that could mean a different note."""
    mv, allowed_dirs = (
        vault_paths.get_master_vault(),
        vault_paths.get_allowed_dirs(profile),
    )
    if not mv or not allowed_dirs:
        return NOTE_DENIED
    src = resolve_existing_note(profile, old_name)
    if src is None:
        return NOTE_NOT_FOUND

    dst, error = _resolve_rename_destination(mv, allowed_dirs, src, new_name)
    if error:
        return error

    old_rel, new_rel = os.path.relpath(src, mv), os.path.relpath(dst, mv)
    old_stem = os.path.splitext(os.path.basename(src))[0]
    new_stem = os.path.splitext(os.path.basename(dst))[0]
    ref_files = sorted({b["rel_path"] for b in get_backlinks_fn(profile, old_stem)})
    old_rel_norm = old_rel.replace("\\", "/")
    same_stem_paths = {
        p.replace("\\", "/")
        for p in find_notes_by_stem_fn(profile, old_stem)
        if p.replace("\\", "/") != old_rel_norm
    }

    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.rename(src, dst)
    except OSError as e:
        return f"Error: Failed to rename note: {e}"

    updated = _relink_referencing_notes(
        mv,
        allowed_dirs,
        ref_files,
        old_rel,
        new_rel,
        dst,
        new_stem,
        same_stem_paths,
        reindex_hook,
        manifest_hook,
    )

    ws = _workspace_dir()
    ignore = config_manager.get("vault.ignore_folders") or []
    try:
        vault_index.remove_note(ws, mv, old_rel)
        vault_manifest.remove_note(ws, mv, old_rel, ignore_folders=ignore)
    except Exception:
        log.debug("[vault] rename de-index failed for %s", old_rel, exc_info=True)
    reindex_hook(mv, dst)
    manifest_hook(mv, dst)
    on_backlinks_changed()

    tail = f" ({updated} file{'s' if updated != 1 else ''} relinked)" if updated else ""
    return f"Renamed to `{new_rel}`{tail}"


def delete_note(
    profile: dict[str, Any],
    note_name: str,
    *,
    on_backlinks_changed: Callable[[], None] = _NOOP_CALLBACK,
) -> str:
    """Move a vault note to `<vault>/.trash/` preserving its relative path
    (ADR-084) — recoverable, and `.trash` is already an ignored folder. A
    name clash in the trash gets a timestamp suffix."""
    mv, allowed_dirs = (
        vault_paths.get_master_vault(),
        vault_paths.get_allowed_dirs(profile),
    )
    if not mv or not allowed_dirs:
        return NOTE_DENIED
    src = resolve_existing_note(profile, note_name)
    if src is None:
        return NOTE_NOT_FOUND
    if not any(is_safe_path(src, allowed) for allowed in allowed_dirs):
        return NOTE_DENIED

    old_rel = os.path.relpath(src, mv)
    dest = os.path.join(mv, vault_trash.TRASH_DIRNAME, old_rel)
    # `get_allowed_dirs` only ever returns folders under `mv`, so `old_rel`
    # can't carry a `..` prefix — but assert the trash target stays in-bounds
    # rather than trust that invariant from a distance.
    if not is_safe_path(dest, mv):
        return NOTE_DENIED
    troot = os.path.join(mv, vault_trash.TRASH_DIRNAME)
    clashed = False
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            stem, ext = os.path.splitext(dest)
            dest = f"{stem}-{datetime.datetime.now().astimezone().strftime('%Y%m%d%H%M%S')}{ext}"
            clashed = True
        os.rename(src, dest)
        # `os.rename` keeps the note's own mtime; stamp it to now so the
        # trash view's "deleted N ago" (ADR-085) reflects the deletion, not
        # the last edit.
        os.utime(dest, None)
    except OSError as e:
        return f"Error: Failed to delete note: {e}"
    if clashed:
        # D4: record the real original path explicitly rather than leaving
        # it to be inferred later from the suffixed filename, which
        # false-positives on a legitimately timestamp-named note.
        dest_rel = os.path.relpath(dest, troot).replace(os.sep, "/")
        vault_trash.record_clash(troot, dest_rel, old_rel)

    ws = _workspace_dir()
    try:
        vault_index.remove_note(ws, mv, old_rel)
        vault_manifest.remove_note(
            ws,
            mv,
            old_rel,
            ignore_folders=config_manager.get("vault.ignore_folders") or [],
        )
    except Exception:
        log.debug("[vault] delete de-index failed for %s", old_rel, exc_info=True)
    on_backlinks_changed()
    return f"Moved to the bin: `{os.path.relpath(dest, mv)}`"


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
