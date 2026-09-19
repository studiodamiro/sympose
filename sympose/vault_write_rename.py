"""
Renaming a vault note and rewriting every `[[wikilink]]` that pointed at it
(ADR-084/D3, split out of vault_write.py).
"""

import logging
import os
import re
from typing import Any, Callable

from sympose import vault_index, vault_manifest, vault_paths
from sympose.config import config_manager, is_safe_path
from sympose.vault_write_core import _workspace_dir
from sympose.vault_write_resolve import resolve_existing_note
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS, NOTE_NOT_FOUND, _NOOP_CALLBACK, _NOOP_HOOK

log = logging.getLogger(__name__)

_WIKILINK_RE = re.compile(r"(!?)\[\[([^\[\]\r\n]+?)\]\]")


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
