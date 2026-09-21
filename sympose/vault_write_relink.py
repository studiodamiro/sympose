"""
Rewriting `[[wikilink]]` references after a rename — split out of
`vault_write_rename.py` (project's 200-LOC-per-file guideline).
"""

import logging
import os
import re

from sympose.security import is_safe_path
from sympose.vault_write import get_file_lock

log = logging.getLogger(__name__)

# Structurally reserved in `[[wikilink]]` syntax (`]` closes the link, `|`
# starts an alias, `#` starts a heading anchor) — a new stem containing any
# of these would silently corrupt every backlink rewritten to point at it.
WIKILINK_UNSAFE_CHARS = frozenset("[]|#")

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

    A bare `[[old_stem]]` is only rewritten unconditionally when no other
    real note shares that stem (`same_stem_paths` empty); otherwise it's
    only rewritten when this occurrence's own file sits in the renamed
    note's own top-level folder — Obsidian's own preference for resolving
    an unqualified link — leaving it alone rather than guessing at the
    others. A link already folder-qualified in its own text is unaffected
    by that ambiguity: it's only rewritten when its qualifying segments
    actually match the renamed note's own path."""
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


def relink_referencing_notes(
    mv: str,
    allowed_dirs: list[str],
    ref_files: list[str],
    old_rel: str,
    new_rel: str,
    dst: str,
    new_stem: str,
    same_stem_paths: set[str],
) -> tuple[int, int]:
    """Returns (updated, failed) — `failed` counts a referencing file whose
    rewrite was attempted but lost to an OSError (permissions, a concurrent
    move/delete, ...), so a caller can tell the difference between "nothing
    needed relinking" and "some relinks silently didn't happen"."""
    updated = 0
    failed = 0
    for rel in ref_files:
        # The renamed note's own self-referencing wikilinks live at its
        # *new* path now — `fp` would point at `src`, which no longer
        # exists post-rename.
        fp = dst if rel == old_rel else os.path.join(mv, rel)
        source_rel = new_rel if rel == old_rel else rel
        if not os.path.isfile(fp) or not any(
            is_safe_path(fp, allowed) for allowed in allowed_dirs
        ):
            continue
        try:
            with get_file_lock(fp):
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                rewritten, hits = rewrite_wikilink_targets(
                    content, old_rel, new_stem, source_rel, same_stem_paths
                )
                if not hits:
                    continue
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(rewritten)
            updated += 1
        except OSError as e:
            log.warning("[vault] relink failed for %s after renaming %s: %s", fp, old_rel, e)
            failed += 1
    return updated, failed
