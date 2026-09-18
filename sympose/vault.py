"""
Sandboxed Vault & Markdown Note Manager for Sympose.
"""

import logging
import os
import re
from typing import Any, ClassVar

import yaml

from sympose import (
    vault_grounding,
    vault_links,
    vault_paths,
    vault_recall,
    vault_search,
    vault_trash,
    vault_write,
    vault_write_concurrency,
)
from sympose.config import config_manager
from sympose.vault_folders import FoldersMixin
from sympose.vault_graph import GraphMixin
from sympose.vault_note_read import NoteReadMixin
from sympose.vault_note_target import NoteTargetMixin
from sympose.vault_snapshot import SnapshotMixin
from sympose.vault_turn_context import TurnContextMixin

log = logging.getLogger(__name__)

# Extracts every vault note path a piece of text names - shared by
# PersonaEngine (comparing a reply against its injected vault_ctx) and
# SubAgentEngine (comparing a sub-agent's synthesis against its own
# tool-call history) so both can catch a model naming/quoting a note it
# was never actually given, without a second model call to compare meaning.
VAULT_PATH_TOKEN_RE = re.compile(
    r"[\w][\w \-]*(?:/[\w][\w \-]*)+\.(?:md|markdown|txt)\b", re.IGNORECASE
)

# ADR-124's structural referent check can run 2-3x in a single strict-
# grounding turn (the user's continuation, the prior assistant turn, the
# reply itself); without this, each call rebuilds the same frozenset from
# the whole vault snapshot from scratch. Same mtime-keyed shape as the two
# caches above - `_get_vault_snapshot`/`get_discovered_folders` are already
# cached, so this only saves the Python-level aggregation over their output,
# not any I/O.
_REAL_VAULT_REFERENTS_CACHE: dict[tuple[str, ...], tuple[float, frozenset]] = {}


class VaultManager(
    SnapshotMixin,
    GraphMixin,
    NoteReadMixin,
    NoteTargetMixin,
    FoldersMixin,
    TurnContextMixin,
):
    """Manages sandboxed reading, writing, high-density manifests, and searching in Obsidian vaults."""

    # ------------------------------------------------------------------
    # Conversational-recall subject extraction — thin wrappers over
    # `vault_recall`, which owns the pure text-processing logic. The
    # orchestrator that actually *uses* this (resolve_turn_context, below)
    # stays here — see vault_recall.py's own module docstring for why.
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_recall_subject(message: str) -> tuple[str, bool]:
        """Best-effort extraction of the *subject* of a conversational recall
        request: 'pull up my notes on Rilke' -> 'rilke', 'what did I write about
        grief in my journal' -> 'grief'. Substring search needs a tight phrase;
        the whole lead-in-plus-subject string matches nothing. Returns
        (subject, had_leadin) — had_leadin is True when a recall phrasing
        ('tell me about', 'pull up', …) was consumed, which is itself a signal
        of vault intent even absent a trigger keyword."""
        return vault_recall.extract_recall_subject(message)

    @classmethod
    def has_recall_intent(cls, message: str) -> bool:
        """True when the message is itself a fresh vault-recall request (a recall
        lead-in was consumed, or a configured search trigger appears). The engine
        uses this to decide *not* to reuse a previous turn's injected vault
        context when the current turn asked its own vault question and retrieval
        came back empty — answering a fresh 'pull up X' from a stale unrelated
        note is exactly the fabrication this guards against."""
        return vault_recall.has_recall_intent(message)

    # ------------------------------------------------------------------
    # Structural claim/intent checking (ADR-124) — thin wrappers over
    # `vault_grounding`, which owns the pure logic, the same split as the
    # recall-subject wrappers above. This backs (does not replace) the
    # phrase-based checks above and in engine.py's `_VAULT_CLAIM_RE`: it
    # catches a message or reply naming something real in the vault no
    # matter how it's worded, which a fixed phrase list can never fully
    # enumerate.
    # ------------------------------------------------------------------

    @classmethod
    def real_vault_referents(cls, profile: dict[str, Any]) -> frozenset[str]:
        """Lowercased ground truth for `first_unverified_referent`: every
        real folder name, note filename stem, and frontmatter title in this
        profile's allowed vault scope. Built from the same cached folder
        discovery and snapshot data other vault reads already use - no new
        I/O pattern, no LLM call. Cached itself (mtime-keyed, like
        `_get_vault_snapshot`) since a single strict-grounding turn can call
        this 2-3x - see ADR-124."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return frozenset()
        raw_ignore = config_manager.get("vault.ignore_folders")
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        cache_key = (tuple(sorted(allowed_dirs)), tuple(sorted(ignore_dirs)))
        current_mtime = vault_paths.dirs_mtime(allowed_dirs, ignore_dirs)
        cached_mtime, cached_referents = _REAL_VAULT_REFERENTS_CACHE.get(
            cache_key, (0.0, frozenset())
        )
        if current_mtime == cached_mtime and cached_referents:
            return cached_referents
        referents = vault_grounding.real_vault_referents_from_snapshot(
            cls.get_discovered_folders(profile),
            cls._get_vault_snapshot(mv, allowed_dirs),
        )
        _REAL_VAULT_REFERENTS_CACHE[cache_key] = (current_mtime, referents)
        return referents

    @classmethod
    def first_unverified_referent(
        cls,
        text: str,
        profile: dict[str, Any],
        extra_stop: frozenset[str] | set[str] = frozenset(),
    ) -> str:
        """First real folder/note/title named in `text`, regardless of
        wording - the structural check that backs the phrase-based
        claim/intent detection in this module and in engine.py. See
        ADR-124."""
        return vault_grounding.first_unverified_referent(
            text, VAULT_PATH_TOKEN_RE, cls.real_vault_referents(profile), extra_stop
        )

    @classmethod
    def real_referent_mentioned(
        cls,
        text: str,
        profile: dict[str, Any],
        extra_stop: frozenset[str] | set[str] = frozenset(),
    ) -> str:
        """Case-insensitive counterpart to `first_unverified_referent`, for
        inbound chat that can't be assumed to follow Title-Case
        conventions. See ADR-123.5."""
        return vault_grounding.real_referent_mentioned(
            text, cls.real_vault_referents(profile), extra_stop
        )

    # Sandbox path resolution itself now lives in vault_paths.py (pure,
    # self-contained, no other vault module depends on it) — these stay as
    # thin re-exports so every existing `VaultManager.get_allowed_dirs(...)`
    # call site across the app keeps working unchanged.
    @staticmethod
    def _get_master_vault() -> str | None:
        return vault_paths.get_master_vault()

    @classmethod
    def get_vault_name(cls) -> str | None:
        return vault_paths.get_vault_name()

    @classmethod
    def get_allowed_dirs(cls, profile: dict[str, Any]) -> list[str]:
        return vault_paths.get_allowed_dirs(profile)

    @classmethod
    def get_primary_dir(cls, profile: dict[str, Any]) -> str | None:
        return vault_paths.get_primary_dir(profile)

    @classmethod
    def describes_random_pull_ritual(cls, fact: str) -> bool:
        """Generic detector for a persona-memory fact that itself describes
        a "pull a random note and discuss it" ritual - see
        vault_recall.describes_random_pull_ritual for the actual check."""
        return vault_recall.describes_random_pull_ritual(fact)

    @staticmethod
    def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
        """Extracts YAML frontmatter dictionary and clean markdown body."""
        if not content.startswith("---"):
            return {}, content

        # Closing `---` may be the last line of the file (frontmatter-only note),
        # carry trailing spaces, or be followed by a body. All three are valid.
        match = re.match(
            r"^---\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n(.*))?\Z", content, re.DOTALL
        )
        if not match:
            return {}, content

        raw_yaml, body = match.group(1), match.group(2) or ""
        meta: dict[str, Any] = {}
        try:
            parsed = yaml.safe_load(raw_yaml)
            if isinstance(parsed, dict):
                meta = parsed
        except Exception as e:
            log.debug("YAML frontmatter parse failed, falling back to line scan: %s", e)

        if not meta:
            for line in raw_yaml.splitlines():
                if ":" in line and not line.strip().startswith("#"):
                    k, v = line.split(":", 1)
                    k = k.strip().lower()
                    v = v.strip().strip("\"'")
                    if v:
                        meta[k] = v
        return meta, body

    # ------------------------------------------------------------------
    # Search — thin wrappers over `vault_search`, which owns the query
    # logic and the per-persona last-search cache; `_get_vault_snapshot`
    # stays here since reindex hooks / manifest / graph building need it
    # too, so it's passed down as a hook rather than owned by the search
    # module.
    # ------------------------------------------------------------------

    @classmethod
    def search_structured(
        cls,
        profile: dict[str, Any],
        query: str,
        target_folder: str | None = None,
        max_results: int = 15,
    ) -> list[dict[str, Any]]:
        """Performs fast sandboxed vault search returning structured match metadata with snippets."""
        return vault_search.search_structured(
            profile,
            query,
            target_folder,
            max_results,
            get_vault_snapshot_fn=cls._get_vault_snapshot,
        )

    @classmethod
    def get_last_search(cls, profile: dict[str, Any]) -> list[dict[str, Any]]:
        """Returns the most recent search results for the given profile."""
        return vault_search.get_last_search(profile)

    @classmethod
    def format_search_digest(cls, query: str, results: list[dict[str, Any]]) -> str:
        """Formats structured search results into a clean, high-density Markdown list."""
        return vault_search.format_search_digest(query, results)

    @classmethod
    def search(
        cls, profile: dict[str, Any], query: str, target_folder: str | None = None
    ) -> str:
        return vault_search.search(
            profile,
            query,
            target_folder,
            get_vault_snapshot_fn=cls._get_vault_snapshot,
        )

    # ------------------------------------------------------------------
    # Wikilinks & backlinks — thin wrappers over `vault_links`, which owns
    # the inverted index and its cache.
    # ------------------------------------------------------------------

    @staticmethod
    def extract_wikilinks(content: str) -> list[dict[str, Any]]:
        """Extracts structured wikilink metadata from text content, supporting aliases and heading anchors."""
        return vault_links.extract_wikilinks(content)

    @classmethod
    def get_forward_links(
        cls, profile: dict[str, Any], note_name: str
    ) -> list[dict[str, Any]]:
        """Extracts all outgoing wikilinks from a given note within allowed vault folders."""
        return vault_links.get_forward_links(
            profile, note_name, read_note_fn=cls.read_note
        )

    @classmethod
    def build_backlink_index(
        cls, profile: dict[str, Any]
    ) -> dict[str, list[dict[str, Any]]]:
        """Constructs an inverted backlink index, using a mtime cache to skip re-walks on unchanged vaults."""
        return vault_links.build_backlink_index(profile)

    @classmethod
    def get_backlinks(
        cls, profile: dict[str, Any], note_name: str
    ) -> list[dict[str, Any]]:
        """Queries the in-memory inverted index for all incoming references to note_name."""
        return vault_links.get_backlinks(profile, note_name)

    @classmethod
    def get_backlinks_digest(
        cls, profile: dict[str, Any], note_name: str, max_entries: int = 15
    ) -> str:
        """Generates a high-density Markdown summary of backlinks for note_name."""
        return vault_links.get_backlinks_digest(profile, note_name, max_entries)

    @staticmethod
    def format_manifest_digest(
        manifest: dict[str, Any],
        max_folders: int = 30,
        max_tags: int = 12,
        max_hubs: int = 8,
    ) -> str:
        """Compact, disk-true structural map from an ADR-078 manifest — folder
        counts, top tags, most-linked notes, unresolved links. Structure only:
        no note text, so it says *where* to look, never *what a note says*."""
        return vault_links.format_manifest_digest(
            manifest, max_folders, max_tags, max_hubs
        )

    # ------------------------------------------------------------------
    # Note/folder mutation — thin, sandbox-scoped wrappers over
    # `vault_write`, which owns the filesystem mechanics; this class owns
    # the reindex/manifest/backlink-cache side effects that follow a
    # successful write, via hooks passed into each call (same shape as the
    # trash wrappers below).
    # ------------------------------------------------------------------

    NOTE_NOT_FOUND = vault_write.NOTE_NOT_FOUND
    NOTE_DENIED = vault_write.NOTE_DENIED
    NOTE_EXISTS = vault_write.NOTE_EXISTS
    NOTE_CONFLICT = vault_write_concurrency.NOTE_CONFLICT

    @classmethod
    def get_template_for_path(cls, mv: str, note_name: str) -> str | None:
        return vault_write.get_template_for_path(mv, note_name)

    @classmethod
    def get_note_mtime(cls, profile: dict[str, Any], note_name: str) -> float | None:
        """Current on-disk mtime of the file `read_note` would open for
        `note_name`, or None if it doesn't exist yet. The precondition a
        caller round-trips back as `expected_mtime` on a later write, for
        the optimistic-concurrency guard (ADR-129)."""
        target = cls._resolve_existing_note(profile, note_name)
        return vault_write_concurrency.current_mtime(target) if target else None

    @classmethod
    def write_note(
        cls,
        profile: dict[str, Any],
        note_name: str,
        content: str,
        *,
        expected_mtime: float | None = None,
    ) -> str:
        return vault_write.write_note(
            profile,
            note_name,
            content,
            reindex_hook=cls._reindex_note_if_enabled,
            manifest_hook=cls._update_manifest_if_enabled,
            expected_mtime=expected_mtime,
        )

    @classmethod
    def append_note(
        cls,
        profile: dict[str, Any],
        note_name: str,
        content: str,
        *,
        expected_mtime: float | None = None,
    ) -> str:
        return vault_write.append_note(
            profile,
            note_name,
            content,
            reindex_hook=cls._reindex_note_if_enabled,
            manifest_hook=cls._update_manifest_if_enabled,
            expected_mtime=expected_mtime,
        )

    @classmethod
    def overwrite_note(
        cls,
        profile: dict[str, Any],
        note_name: str,
        content: str,
        *,
        expected_mtime: float | None = None,
    ) -> str:
        """Replace an *existing* vault note's file with `content`, verbatim (the
        editor already owns the whole document, frontmatter included). Resolves
        the same file `read_note` would return, so a dashboard save lands back on
        the note it was opened from. Overwrite only — a path with no existing
        file returns `NOTE_NOT_FOUND` rather than creating one (ADR-081); a path
        outside the persona's sandbox returns `NOTE_DENIED`; a caller-supplied
        `expected_mtime` that no longer matches the file on disk returns
        `NOTE_CONFLICT` instead of clobbering a concurrent write (ADR-129). On
        success the note is re-indexed and the manifest refreshed, exactly as
        `write_note` does.
        """
        return vault_write.overwrite_note(
            profile,
            note_name,
            content,
            reindex_hook=cls._reindex_note_if_enabled,
            manifest_hook=cls._update_manifest_if_enabled,
            expected_mtime=expected_mtime,
        )

    @classmethod
    def create_note(
        cls, profile: dict[str, Any], note_name: str, content: str | None = None
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
        return vault_write.create_note(
            profile,
            note_name,
            content,
            reindex_hook=cls._reindex_note_if_enabled,
            manifest_hook=cls._update_manifest_if_enabled,
        )

    @classmethod
    def create_folder(cls, profile: dict[str, Any], folder_name: str) -> str:
        """Create a new *empty* folder under the vault (ADR-095), alongside
        `create_note`'s path resolution and sandbox rules: `folder_name` is
        relative to the vault and lands under the master vault when it
        contains a separator, otherwise in the persona's primary folder.
        `NOTE_EXISTS` when the path is already a file or directory,
        `NOTE_DENIED` outside the sandbox."""
        return vault_write.create_folder(profile, folder_name)

    @classmethod
    def delete_folder(cls, profile: dict[str, Any], folder_name: str) -> str:
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
        return vault_write.delete_folder(
            profile, folder_name, on_backlinks_changed=vault_links.clear_cache
        )

    @classmethod
    def _resolve_existing_note(
        cls, profile: dict[str, Any], note_name: str
    ) -> str | None:
        """Absolute path of the file `read_note` would open for `note_name`, or
        `None`: direct path under the master vault → basename in an allowed
        folder → recursive case-insensitive stem match. Shared by
        `overwrite_note` / `rename_note` / `delete_note`."""
        return vault_write.resolve_existing_note(profile, note_name)

    @classmethod
    def _find_notes_by_stem(cls, profile: dict[str, Any], stem: str) -> list[str]:
        """Vault-relative paths of every real note sharing `stem` (D3) — lets
        `rename_note` tell an unambiguous bare wikilink from one that could
        mean a different, same-named note elsewhere."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return []
        want = stem.strip().lower()
        return [
            entry["rel_path"]
            for entry in cls._get_vault_snapshot(mv, allowed_dirs)
            if os.path.splitext(entry["file_name"])[0].lower() == want
        ]

    @classmethod
    def rename_note(cls, profile: dict[str, Any], old_name: str, new_name: str) -> str:
        """Rename a vault note and rewrite every `[[wikilink]]` that pointed at
        it (ADR-084). `new_name` stays in the same folder unless it carries a
        separator. `NOTE_NOT_FOUND` / `NOTE_EXISTS` / `NOTE_DENIED` as for the
        other note ops."""
        return vault_write.rename_note(
            profile,
            old_name,
            new_name,
            get_backlinks_fn=cls.get_backlinks,
            find_notes_by_stem_fn=cls._find_notes_by_stem,
            reindex_hook=cls._reindex_note_if_enabled,
            manifest_hook=cls._update_manifest_if_enabled,
            on_backlinks_changed=vault_links.clear_cache,
        )

    @classmethod
    def delete_note(cls, profile: dict[str, Any], note_name: str) -> str:
        """Move a vault note to `<vault>/.trash/` preserving its relative path
        (ADR-084) — recoverable, and `.trash` is already an ignored folder. A
        name clash in the trash gets a timestamp suffix."""
        return vault_write.delete_note(
            profile, note_name, on_backlinks_changed=vault_links.clear_cache
        )

    # ------------------------------------------------------------------
    # Trash recovery (ADR-085) — thin, sandbox-scoped wrappers over
    # `vault_trash`. Restore re-indexes the note so it is searchable and
    # back on the graph immediately; purge needs nothing (the file left
    # the index when it was trashed).
    # ------------------------------------------------------------------

    _TRASH_SENTINEL_MAP: ClassVar[dict[Any, Any]] = {
        vault_trash.NOT_IN_TRASH: NOTE_NOT_FOUND,
        vault_trash.TARGET_EXISTS: NOTE_EXISTS,
        vault_trash.DENIED: NOTE_DENIED,
    }

    @classmethod
    def list_trash(cls, profile: dict[str, Any]) -> list[dict[str, Any]]:
        """Recoverable notes in `<vault>/.trash`, scoped to the persona's allowed
        folders, newest deletion first (ADR-085)."""
        mv, allowed = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed:
            return []
        return vault_trash.list_trashed(mv, allowed)

    @classmethod
    def restore_from_trash(cls, profile: dict[str, Any], trash_path: str) -> str:
        """Move a trashed note back to its original path (ADR-085).
        `NOTE_NOT_FOUND` if it isn't in the trash, `NOTE_EXISTS` if something
        occupies the original spot now, `NOTE_DENIED` outside the sandbox."""
        mv, allowed = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed:
            return cls.NOTE_DENIED
        result = vault_trash.restore(mv, allowed, trash_path)
        if result in cls._TRASH_SENTINEL_MAP:
            return cls._TRASH_SENTINEL_MAP[result]
        if result.startswith("Error:"):
            return result
        dst = os.path.join(mv, result)
        cls._reindex_note_if_enabled(mv, dst)
        cls._update_manifest_if_enabled(mv, dst)
        vault_links.clear_cache()
        return f"Restored to `{result}`"

    @classmethod
    def purge_from_trash(cls, profile: dict[str, Any], trash_path: str) -> str:
        """Permanently delete one trashed note (ADR-085). `NOTE_NOT_FOUND` /
        `NOTE_DENIED` as above. Irreversible — the client guards it behind a
        confirm dialog."""
        mv, allowed = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed:
            return cls.NOTE_DENIED
        result = vault_trash.purge(mv, allowed, trash_path)
        if result in cls._TRASH_SENTINEL_MAP:
            return cls._TRASH_SENTINEL_MAP[result]
        if result.startswith("Error:"):
            return result
        return "Deleted permanently"

    @classmethod
    def empty_trash(cls, profile: dict[str, Any]) -> str:
        """Permanently delete every in-scope trashed note (ADR-085)."""
        mv, allowed = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed:
            return cls.NOTE_DENIED
        n = vault_trash.purge_all(mv, allowed)
        return f"Emptied the bin ({n} note{'s' if n != 1 else ''})"

    @classmethod
    def _sync_frontmatter_tags(cls, file_path: str, new_tags: list[str]) -> None:
        """Dynamically merges new tags into the file's YAML frontmatter block."""
        vault_write.sync_frontmatter_tags(file_path, new_tags)

    @classmethod
    def write_daily_note(cls, profile: dict[str, Any], reflection: str) -> str:
        return vault_write.write_daily_note(
            profile,
            reflection,
            reindex_hook=cls._reindex_note_if_enabled,
            manifest_hook=cls._update_manifest_if_enabled,
        )

    @classmethod
    def write_session_note(
        cls,
        profile: dict[str, Any],
        summary_md: str,
        subfolder: str = "Sessions",
        session_title: str | None = None,
    ) -> str:
        return vault_write.write_session_note(
            profile, summary_md, subfolder, session_title
        )
