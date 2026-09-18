"""
LLM Wiki Layer Bootstrap for Sympose (ADR-132).

Seeds the opt-in Tier-3 "LLM Wiki" scaffolding — a schema file, a raw
sources subfolder, and an append-only log — the first time a persona whose
sandbox reaches `wiki.root` gets bootstrapped. No-op entirely when
`wiki.root` is unset (the default), so a user who never touches this
feature pays zero cost.

Hooked into `ProfileManager.bootstrap_missing_artifacts`, the same "seed
missing artifacts on every reload" pass already used for soul/memory
files — but unlike that pass, this one writes into the *vault*, not the
workspace `profiles/` directory, via the existing `vault_write.create_note`/
`create_folder` (refuses rather than overwrites), so a user's own edits to
these files are never clobbered on a later reload, and a persona whose
`vault_folders` doesn't reach `wiki.root` harmlessly no-ops (NOTE_DENIED)
rather than erroring.
"""

import logging
from typing import Any

from sympose import vault_write
from sympose.config import config_manager

log = logging.getLogger(__name__)

_SCHEMA_TEMPLATE = """\
# {root} — LLM Wiki Schema

This folder is an opt-in Tier-3 "LLM Wiki" (ADR-132), following Andrej \
Karpathy's pattern for AI-maintained knowledge bases: three layers, three \
operations.

## Layers

- **`{sources}/`** — raw sources: originals dropped in here (articles, \
transcripts, notes). Immutable — read, never edited, by any wiki skill.
- **This folder's other pages** — AI-generated/owned markdown: summaries, \
entity pages, concept pages, comparisons. Created and updated by the \
`wiki_ingest` skill; not meant to be hand-authored (though nothing stops \
you from reading or fixing one directly).
- **`{log}`** — chronological, append-only record of every ingest/lint \
event.

## Operations

- **Ingest** — hand a source to a persona whose skills include \
`wiki_ingest`; it files it into pages here and logs the event.
- **Query** — ask any persona with vault-recall access to this folder; no \
dedicated query skill needed, the existing vault search already covers it.
- **Lint** — ask a persona whose skills include `wiki_lint` to health-check \
this folder for contradictions, stale claims, and orphan pages (no \
inbound links). Report-only by default; auto-fix is a per-persona \
opt-in (`lint_auto_fix`).
"""

_LOG_HEADER = "# Wiki Log\n\nAppend-only. Newest entries at the bottom.\n"


def bootstrap_wiki_layer(profile: dict[str, Any]) -> None:
    """No-op unless `wiki.root` is configured. Seeds the schema file, the
    raw-sources subfolder, and an empty log — each only if missing, via
    `create_note`/`create_folder` (refuse rather than overwrite), so this
    is safe to call on every profile reload."""
    root = str(config_manager.get("wiki.root") or "").strip().strip("/")
    if not root:
        return

    sources = str(config_manager.get("wiki.raw_sources_subdir") or "Sources").strip("/")
    schema_file = str(config_manager.get("wiki.schema_file") or "WIKI.md").strip()
    log_file = str(config_manager.get("wiki.log_file") or "log.md").strip()

    vault_write.create_note(
        profile,
        f"{root}/{schema_file}",
        _SCHEMA_TEMPLATE.format(root=root, sources=sources, log=log_file),
    )
    vault_write.create_note(profile, f"{root}/{log_file}", _LOG_HEADER)
    vault_write.create_folder(profile, f"{root}/{sources}")
