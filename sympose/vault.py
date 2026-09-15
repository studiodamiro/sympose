"""
Sandboxed Vault & Markdown Note Manager for Sympose.
"""

import logging
import os
import re
from typing import Any, ClassVar

import yaml

from sympose import (
    vault_index,
    vault_links,
    vault_manifest,
    vault_paths,
    vault_recall,
    vault_search,
    vault_trash,
    vault_tree,
    vault_write,
)
from sympose.config import config_manager, is_safe_path
from sympose.workspace import resolve_workspace_dir

log = logging.getLogger(__name__)

# Extracts every vault note path a piece of text names - shared by
# PersonaEngine (comparing a reply against its injected vault_ctx) and
# SubAgentEngine (comparing a sub-agent's synthesis against its own
# tool-call history) so both can catch a model naming/quoting a note it
# was never actually given, without a second model call to compare meaning.
VAULT_PATH_TOKEN_RE = re.compile(
    r"[\w][\w \-]*(?:/[\w][\w \-]*)+\.(?:md|markdown|txt)\b", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Vault content snapshot cache — avoids re-walking + re-reading every note on
# every search_structured() / get_folder_digest() call. Same mtime-keyed
# invalidation strategy as vault_links' own backlink cache.
# Key: tuple of scanned dir paths → (combined_mtime, flat list of parsed notes)
# ---------------------------------------------------------------------------
_VAULT_SNAPSHOT_CACHE: dict[tuple[str, ...], tuple[float, list[dict[str, Any]]]] = {}


class VaultManager:
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
    def read_note(cls, profile: dict[str, Any], note_name: str) -> str:
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return "⚠️ Master notes directory not configured or access denied."
        clean_name = note_name.strip().strip("\"'")
        if not clean_name.endswith(".md"):
            clean_name += ".md"

        direct_target = os.path.join(mv, clean_name)
        for allowed in allowed_dirs:
            if is_safe_path(direct_target, allowed) and os.path.exists(direct_target):
                try:
                    with open(
                        direct_target, "r", encoding="utf-8", errors="ignore"
                    ) as f:
                        return f.read().strip()
                except Exception as e:
                    return f"Error reading note `{clean_name}`: {e}"

        for allowed in allowed_dirs:
            target = os.path.join(allowed, os.path.basename(clean_name))
            if is_safe_path(target, allowed) and os.path.exists(target):
                try:
                    with open(target, "r", encoding="utf-8", errors="ignore") as f:
                        return f.read().strip()
                except Exception as e:
                    return f"Error reading note `{clean_name}`: {e}"

        # Recursive case-insensitive / title lookup in allowed folders
        stem_target = os.path.splitext(os.path.basename(clean_name))[0].lower()
        raw_ignore = config_manager.get("vault.ignore_folders") or [
            ".obsidian",
            ".git",
            "Attachments",
            ".trash",
        ]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        for allowed in allowed_dirs:
            for root, dirs, files in os.walk(allowed):
                dirs[:] = [
                    d
                    for d in dirs
                    if d.lower() not in ignore_dirs and not d.startswith(".")
                ]
                for fn in files:
                    if fn.endswith((".md", ".markdown", ".txt")):
                        if os.path.splitext(fn)[0].lower() == stem_target:
                            fp = os.path.join(root, fn)
                            if is_safe_path(fp, allowed):
                                try:
                                    with open(
                                        fp, "r", encoding="utf-8", errors="ignore"
                                    ) as f:
                                        return f.read().strip()
                                except Exception as e:
                                    return f"Error reading note `{clean_name}`: {e}"

        return f"Note `{clean_name}` not found in allowed vault folders."

    @classmethod
    def resolve_asset_path(cls, profile: dict[str, Any], asset_name: str) -> str | None:
        """Resolves a `![[ref]]` embed reference to an absolute file path within
        the persona's sandbox — same three-tier lookup as `read_note` (direct
        join, basename in each allowed dir, recursive walk), but for any file
        and matched on the full filename rather than a bare stem, since an
        asset ref always carries its extension (`diagram.png`, not `diagram`).
        Deliberately does not consult `vault.ignore_folders`: that list exists
        to keep attachment folders out of the *note* index/search/backlinks,
        and its own default names "Attachments" — exactly where embedded
        images typically live, so applying it here would make them
        unreachable. Only dot-directories (`.git`, `.obsidian`, `.trash`, …)
        are skipped."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return None
        clean_name = asset_name.strip().strip("\"'")
        if not clean_name:
            return None

        direct_target = os.path.join(mv, clean_name)
        for allowed in allowed_dirs:
            if is_safe_path(direct_target, allowed) and os.path.isfile(direct_target):
                return direct_target

        for allowed in allowed_dirs:
            target = os.path.join(allowed, os.path.basename(clean_name))
            if is_safe_path(target, allowed) and os.path.isfile(target):
                return target

        want = os.path.basename(clean_name).lower()
        for allowed in allowed_dirs:
            for root, dirs, files in os.walk(allowed):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for fn in files:
                    if fn.lower() == want:
                        fp = os.path.join(root, fn)
                        if is_safe_path(fp, allowed):
                            return fp

        return None

    @classmethod
    def get_folder_digest(
        cls, profile: dict[str, Any], folder_name: str, max_files: int = 50
    ) -> str:
        """Extracts high-density 1-line metadata for all notes in a folder for comprehensive synthesis."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return "⚠️ Master notes directory not configured or access denied."
        target_dir = next(
            (
                d
                for d in allowed_dirs
                if os.path.basename(d).lower() == folder_name.lower()
            ),
            None,
        )
        if not target_dir:
            for d in allowed_dirs:
                candidate = os.path.join(d, folder_name)
                if os.path.exists(candidate) and is_safe_path(candidate, d):
                    target_dir = candidate
                    break
        if not target_dir or not os.path.exists(target_dir):
            return f"Folder `{folder_name}` not found in allowed vault directories."

        entries: list[str] = []
        for entry in cls._get_vault_snapshot(mv, [target_dir])[:max_files]:
            fn, head = entry["file_name"], entry["full_content"][:1000]
            parts = []
            for k in (
                "name",
                "title",
                "aka",
                "tags",
                "birthday",
                "created",
                "up",
                "author",
            ):
                m = re.search(
                    rf"^{k}:\s*([^\n\r]+)", head, re.MULTILINE | re.IGNORECASE
                )
                if (
                    m
                    and m.group(1).strip()
                    and not m.group(1).strip().startswith(("-", "["))
                ):
                    parts.append(f"{k.capitalize()}: {m.group(1).strip()}")
                else:
                    sub = re.findall(
                        rf"^{k}:(?:\s*\n)((?:\s+-\s+[^\n]+\n)+)",
                        head,
                        re.MULTILINE | re.IGNORECASE,
                    )
                    if sub:
                        items = [
                            x.strip("- \t\n\"'") for x in sub[0].strip().split("\n")
                        ]
                        parts.append(f"{k.capitalize()}: {', '.join(items)}")
            fl = next(
                (
                    line.strip("# \t\r")
                    for line in head.split("\n")
                    if line.strip() and not line.startswith("---") and ":" not in line
                ),
                "",
            )
            summary = " | ".join(parts) if parts else fl[:80]
            entries.append(f"- `{fn}`: {summary}" if summary else f"- `{fn}`")

        return (
            f"### High-Density Folder Digest (`{folder_name}/` - {len(entries)} notes):\n"
            + "\n".join(entries)
            if entries
            else f"No notes found in `{folder_name}/`."
        )

    @classmethod
    def get_random_sample_notes(
        cls, profile: dict[str, Any], folder_name: str, count: int = 2
    ) -> str:
        """Extracts real note bodies from 1-3 randomly sampled notes in the folder so the model has true ground-truth content."""
        import random

        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return "⚠️ Master notes directory not configured or access denied."
        target_dir = next(
            (
                d
                for d in allowed_dirs
                if os.path.basename(d).lower() == folder_name.lower()
            ),
            None,
        )
        if not target_dir:
            for d in allowed_dirs:
                candidate = os.path.join(d, folder_name)
                if os.path.exists(candidate) and is_safe_path(candidate, d):
                    target_dir = candidate
                    break
        if not target_dir or not os.path.exists(target_dir):
            return ""

        raw_ignore = config_manager.get("vault.ignore_folders") or [
            ".obsidian",
            ".git",
            "Attachments",
            ".trash",
        ]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        valid_files = []
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [
                d
                for d in dirs
                if d.lower() not in ignore_dirs and not d.startswith(".")
            ]
            for fn in files:
                if fn.endswith((".md", ".markdown", ".txt")):
                    valid_files.append(os.path.join(root, fn))

        if not valid_files:
            return ""

        samples = random.sample(valid_files, min(count, len(valid_files)))
        payloads = []
        for fp in samples:
            rel = os.path.relpath(fp, mv)
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    body = f.read().strip()
                if body:
                    payloads.append(
                        f"### Ground-Truth Sandboxed Vault Note (`{rel}` - Exact Content):\n{body[:2500]}"
                    )
            except Exception as e:
                log.debug("Skipping sample note %s: %s", rel, e)
        return "\n\n---\n\n".join(payloads)

    @staticmethod
    def describes_random_pull_ritual(fact: str) -> bool:
        """Generic detector for a persona-memory fact that itself describes
        a "pull a random note and discuss it" ritual, by whatever name the
        user gave it - not tied to any one wording or persona. Used to
        decide whether to honor such a fact for real (below) rather than
        let the model invent a plausible-sounding title."""
        low = (fact or "").lower()
        return "random" in low and any(
            w in low for w in ("note", "entry", "page", "pull", "pulled", "picked")
        )

    @classmethod
    def resolve_ritual_random_pull(
        cls, profile: dict[str, Any], message: str
    ) -> str | None:
        """Live bug: "let's play our favorite game" doesn't match
        `resolve_turn_context`'s own sample-request phrasing ("random",
        "surprise me", "give me a"...), so its structural retrieval never
        fires for it even when the persona's own memory says the game IS a
        random-note pull - leaving the model to invent a plausible-sounding
        note title instead of performing a real one. Called only once a
        matched memory fact has already been confirmed (via
        `describes_random_pull_ritual`) to describe exactly this ritual.
        Folder-scopes to any discovered folder named in the message, the
        same way `resolve_turn_context`'s case 7 does; otherwise samples
        across the whole vault a persona has full access to."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return None
        for folder_name in cls.get_discovered_folders(profile):
            stem = folder_name.rstrip("s")
            if re.search(rf"\b{re.escape(stem)}\w*\b", message, re.IGNORECASE):
                return cls.get_random_sample_notes(profile, folder_name, count=1) or None
        if any(os.path.realpath(d) == os.path.realpath(mv) for d in allowed_dirs):
            return (
                cls.get_random_sample_notes(profile, os.path.basename(mv), count=1)
                or None
            )
        return None

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

    @classmethod
    def _get_vault_snapshot(cls, mv: str, dirs: list[str]) -> list[dict[str, Any]]:
        """Returns a cached, flat list of every note under `dirs` (path, parsed
        frontmatter, body, raw content), rebuilt only when a dir's mtime changes.
        Shared by search_structured() and get_folder_digest() so neither has to
        re-walk + re-read the vault from disk on every call."""
        raw_ignore = config_manager.get("vault.ignore_folders") or [
            ".obsidian",
            ".git",
            "Attachments",
            ".trash",
        ]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        # Folded into the cache key (not just used to filter the walk) so an
        # ignore-list edit invalidates this cache on its own - a changed
        # ignore set doesn't reliably change any directory's own mtime (a
        # newly-unignored folder can easily be *older* than whatever else
        # last touched the vault), so relying on mtime drift alone silently
        # kept serving a snapshot built under the old list.
        cache_key = (tuple(sorted(dirs)), tuple(sorted(ignore_dirs)))
        current_mtime = vault_paths.dirs_mtime(dirs)
        cached_mtime, cached_snapshot = _VAULT_SNAPSHOT_CACHE.get(cache_key, (0.0, []))
        if current_mtime == cached_mtime and cached_snapshot:
            return cached_snapshot

        snapshot: list[dict[str, Any]] = []

        for allowed in dirs:
            if not os.path.exists(allowed):
                continue
            for root, subdirs, files in os.walk(allowed):
                subdirs[:] = [
                    d
                    for d in subdirs
                    if d.lower() not in ignore_dirs and not d.startswith(".")
                ]
                for file in sorted(files):
                    if not file.endswith((".md", ".markdown", ".txt")):
                        continue
                    file_path = os.path.join(root, file)
                    if not is_safe_path(file_path, allowed):
                        continue
                    try:
                        with open(
                            file_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            full_content = f.read()
                    except Exception as e:
                        log.debug(
                            "Skipping unreadable file in snapshot %s: %s", file_path, e
                        )
                        continue
                    meta, body = cls.parse_frontmatter(full_content)
                    snapshot.append(
                        {
                            "file_name": file,
                            "rel_path": os.path.relpath(file_path, mv),
                            "abs_path": file_path,
                            "full_content": full_content,
                            "meta": meta,
                            "body": body,
                        }
                    )

        _VAULT_SNAPSHOT_CACHE[cache_key] = (current_mtime, snapshot)
        return snapshot

    @staticmethod
    def _workspace_dir() -> str:
        return resolve_workspace_dir()

    @classmethod
    def _reindex_note_if_enabled(cls, mv: str, target_file: str) -> None:
        """Best-effort incremental FTS reindex right after a Sympose-driven
        write, so the note is searchable on the very next query without
        waiting on the mtime-drift rebuild path (ADR-070.5). No-op — and
        costs nothing — unless `vault.search_mode: sqlite_fts` is active."""
        if config_manager.get("vault.search_mode", "direct") != "sqlite_fts":
            return
        try:
            with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
                full_content = f.read()
            meta, body = cls.parse_frontmatter(full_content)
            vault_index.upsert_note(
                cls._workspace_dir(),
                mv,
                os.path.relpath(target_file, mv),
                os.path.basename(target_file),
                meta,
                body,
            )
        except Exception:
            log.debug(
                "[vault] incremental FTS reindex failed for %s",
                target_file,
                exc_info=True,
            )

    @classmethod
    def _update_manifest_if_enabled(cls, mv: str, target_file: str) -> None:
        """Best-effort single-node manifest patch right after a Sympose-driven
        write (ADR-078.5). No-op unless `vault.manifest.enabled` is set."""
        if not config_manager.get("vault.manifest.enabled"):
            return
        try:
            with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
                full_content = f.read()
            meta, _ = cls.parse_frontmatter(full_content)
            vault_manifest.patch_note(
                cls._workspace_dir(),
                mv,
                os.path.relpath(target_file, mv),
                meta,
                full_content,
                ignore_folders=config_manager.get("vault.ignore_folders") or [],
            )
        except Exception:
            log.debug(
                "[vault] manifest patch failed for %s", target_file, exc_info=True
            )

    @classmethod
    def get_manifest(cls) -> dict[str, Any] | None:
        """The ADR-078 structural map (nodes, links, folders) for the whole
        vault, built/refreshed on demand. None when `vault.manifest.enabled` is
        off or no vault is set. Navigation only — never a grounding source;
        quoted content is still read from the note itself."""
        if not config_manager.get("vault.manifest.enabled"):
            return None
        mv = cls._get_master_vault()
        if not mv:
            return None
        return vault_manifest.ensure_fresh(
            cls._workspace_dir(),
            mv,
            lambda: cls._get_vault_snapshot(mv, [mv]),
            read_notes=lambda rels: cls._read_note_entries(mv, rels),
            ignore_folders=config_manager.get("vault.ignore_folders") or [],
            debounce=config_manager.get("vault.manifest.check_debounce_seconds"),
            max_nodes=config_manager.get("vault.manifest.max_nodes") or 0,
        )

    @classmethod
    def _read_note_entries(cls, mv: str, rel_paths: list[str]) -> list[dict[str, Any]]:
        """Read + parse just these notes into `_get_vault_snapshot`-shaped
        entries — the reader the ADR-078.4 manifest delta hands to
        `vault_manifest.ensure_fresh` so an external edit re-parses only what
        changed, not the whole vault."""
        out: list[dict[str, Any]] = []
        for rel in rel_paths:
            fp = os.path.join(mv, rel)
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    full_content = f.read()
            except OSError:
                continue
            meta, body = cls.parse_frontmatter(full_content)
            out.append(
                {
                    "file_name": os.path.basename(rel),
                    "rel_path": rel.replace(os.sep, "/"),
                    "abs_path": fp,
                    "full_content": full_content,
                    "meta": meta,
                    "body": body,
                }
            )
        return out

    @classmethod
    def get_vault_graph(cls) -> dict[str, Any]:
        """`NebulaGraph`-shaped projection of the manifest for
        `GET /api/vault/graph`: nodes `{id, label, folder, tags, val, exists}`
        (`val` = link degree + 1, scales the node radius), links
        `{source, target}`. `label` is clipped to ~64 chars — a `Quotes/` note
        is named after the whole quote, which is unreadable on a graph node;
        `id` keeps the full stem for link resolution and search. Falls back to an
        ephemeral in-memory build when `vault.manifest.enabled` is off;
        `{nodes: [], links: []}` with no vault."""
        manifest = cls.get_manifest()
        if manifest is None:
            mv = cls._get_master_vault()
            if not mv:
                return {"nodes": [], "links": []}
            manifest = vault_manifest.build(mv, cls._get_vault_snapshot(mv, [mv]))
        links = manifest.get("links", [])
        degree: dict[str, int] = {}
        for link in links:
            degree[link["source"]] = degree.get(link["source"], 0) + 1
            degree[link["target"]] = degree.get(link["target"], 0) + 1

        def _label(n: dict[str, Any]) -> str:
            raw = str(n.get("title") or n["id"]).strip()
            return raw if len(raw) <= 64 else raw[:63].rstrip() + "…"

        nodes = [
            {
                "id": n["id"],
                "label": _label(n),
                "folder": n["folder"],
                "tags": n.get("tags", []),
                "val": degree.get(n["id"], 0) + 1,
                "exists": n.get("exists", True),
            }
            for n in manifest.get("nodes", [])
        ]
        return {"nodes": nodes, "links": links}

    @classmethod
    def _list_real_folders(cls, mv: str, dirs: list[str]) -> list[str]:
        """Vault-relative paths of every real subdirectory under `dirs` — a
        directory-only walk (no file reads, same ignore list as
        `_get_vault_snapshot`) so `build_tree` can show a folder that exists
        on disk but holds no notes yet (ADR-098)."""
        raw_ignore = config_manager.get("vault.ignore_folders") or [
            ".obsidian",
            ".git",
            "Attachments",
            ".trash",
        ]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        seen: set = set()
        out: list[str] = []
        for base in dirs:
            if not os.path.exists(base):
                continue
            for root, subdirs, _ in os.walk(base):
                subdirs[:] = [
                    d
                    for d in subdirs
                    if d.lower() not in ignore_dirs and not d.startswith(".")
                ]
                for d in subdirs:
                    rel = os.path.relpath(os.path.join(root, d), mv).replace(
                        os.sep, "/"
                    )
                    if rel not in seen:
                        seen.add(rel)
                        out.append(rel)
        return out

    @classmethod
    def get_vault_tree(cls, profile: dict[str, Any]) -> list[dict[str, Any]]:
        """Nested `VaultNode` directory tree for `GET /api/vault/tree`, scoped
        to the persona's allowed folders. Reads the ADR-078 manifest (ephemeral
        in-memory build when `vault.manifest.enabled` is off); `[]` with no
        vault or no readable folders. Navigation only — never grounding."""
        mv = cls._get_master_vault()
        if not mv:
            return []
        allowed_dirs = cls.get_allowed_dirs(profile)
        if not allowed_dirs:
            return []

        mv_real = os.path.realpath(mv)
        prefixes: list[str] = []
        for d in allowed_dirs:
            d_real = os.path.realpath(d)
            if d_real == mv_real:
                prefixes = [""]
                break
            prefixes.append(os.path.relpath(d_real, mv_real).replace(os.sep, "/"))

        manifest = cls.get_manifest()
        if manifest is None:
            manifest = vault_manifest.build(mv, cls._get_vault_snapshot(mv, [mv]))
        real_folders = cls._list_real_folders(mv, allowed_dirs)
        return vault_tree.build_tree(
            manifest.get("nodes", []), prefixes, real_folders, manifest.get("links", [])
        )

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

    @classmethod
    def resolve_note_target(
        cls, profile: dict[str, Any], target: str
    ) -> tuple[str | None, str | None]:
        """Resolves target string (index number, relative path, or filename) to (rel_path, abs_path)."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return None, None

        clean_target = target.strip().strip("\"'")
        cached = vault_search.get_last_search(profile)

        # 1. Number shortcut [1-N]
        if clean_target.isdigit():
            idx = int(clean_target)
            for item in cached:
                if item.get("index") == idx:
                    return item.get("rel_path"), item.get("abs_path")

        # 2. Match exact rel_path or stem in cached results
        t_stem = os.path.splitext(os.path.basename(clean_target))[0].lower()
        for item in cached:
            if (
                item.get("rel_path", "").lower() == clean_target.lower()
                or os.path.splitext(item.get("file_name", ""))[0].lower() == t_stem
            ):
                return item.get("rel_path"), item.get("abs_path")

        # 3. Direct lookup in vault
        target_name = (
            clean_target
            if clean_target.endswith((".md", ".txt"))
            else clean_target + ".md"
        )
        direct_target = os.path.join(mv, target_name)
        for allowed in allowed_dirs:
            if is_safe_path(direct_target, allowed) and os.path.exists(direct_target):
                return os.path.relpath(direct_target, mv), direct_target

        for allowed in allowed_dirs:
            candidate = os.path.join(allowed, os.path.basename(target_name))
            if is_safe_path(candidate, allowed) and os.path.exists(candidate):
                return os.path.relpath(candidate, mv), candidate

        # 4. Recursive lookup in allowed dirs
        raw_ignore = config_manager.get("vault.ignore_folders") or [
            ".obsidian",
            ".git",
            "Attachments",
            ".trash",
        ]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        for allowed in allowed_dirs:
            for root, dirs, files in os.walk(allowed):
                dirs[:] = [
                    d
                    for d in dirs
                    if d.lower() not in ignore_dirs and not d.startswith(".")
                ]
                for fn in files:
                    if os.path.splitext(fn)[0].lower() == t_stem:
                        fp = os.path.join(root, fn)
                        if is_safe_path(fp, allowed):
                            return os.path.relpath(fp, mv), fp

        return None, None

    @classmethod
    def open_in_obsidian(cls, profile: dict[str, Any], target: str) -> tuple[bool, str]:
        """Opens note in Obsidian desktop app / system default editor."""
        import platform
        import subprocess

        rel_path, abs_path = cls.resolve_note_target(profile, target)
        if not abs_path or not os.path.exists(abs_path):
            return False, f"⚠️ Note `{target}` not found in allowed vault folders."

        try:
            system = platform.system()
            if system == "Darwin":
                subprocess.Popen(["open", abs_path])
            elif system == "Linux":
                subprocess.Popen(["xdg-open", abs_path])
            elif system == "Windows":
                os.startfile(abs_path)
            return True, f"✨ Opened `{rel_path}` in Obsidian / system editor."
        except Exception as e:
            return False, f"⚠️ Failed to open note: {e}"

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

    @classmethod
    def get_template_for_path(cls, mv: str, note_name: str) -> str | None:
        return vault_write.get_template_for_path(mv, note_name)

    @classmethod
    def write_note(cls, profile: dict[str, Any], note_name: str, content: str) -> str:
        return vault_write.write_note(
            profile,
            note_name,
            content,
            reindex_hook=cls._reindex_note_if_enabled,
            manifest_hook=cls._update_manifest_if_enabled,
        )

    @classmethod
    def append_note(cls, profile: dict[str, Any], note_name: str, content: str) -> str:
        return vault_write.append_note(
            profile,
            note_name,
            content,
            reindex_hook=cls._reindex_note_if_enabled,
            manifest_hook=cls._update_manifest_if_enabled,
        )

    @classmethod
    def overwrite_note(
        cls, profile: dict[str, Any], note_name: str, content: str
    ) -> str:
        """Replace an *existing* vault note's file with `content`, verbatim (the
        editor already owns the whole document, frontmatter included). Resolves
        the same file `read_note` would return, so a dashboard save lands back on
        the note it was opened from. Overwrite only — a path with no existing
        file returns `NOTE_NOT_FOUND` rather than creating one (ADR-081); a path
        outside the persona's sandbox returns `NOTE_DENIED`. On success the note
        is re-indexed and the manifest refreshed, exactly as `write_note` does.
        """
        return vault_write.overwrite_note(
            profile,
            note_name,
            content,
            reindex_hook=cls._reindex_note_if_enabled,
            manifest_hook=cls._update_manifest_if_enabled,
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
    def _rewrite_wikilink_targets(
        cls, text: str, old_stem: str, new_stem: str
    ) -> tuple[str, int]:
        """Retarget every `[[old]]` / `![[old]]` / `[[old#h]]` / `[[old|a]]`
        (and the `Folder/old` path form) to `new_stem`, leaving any `#heading`
        and `|alias` intact. Returns the rewritten text and the hit count."""
        return vault_write.rewrite_wikilink_targets(text, old_stem, new_stem)

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

    @classmethod
    def has_vault_skill(cls, profile: dict[str, Any]) -> bool:
        """Verifies if the persona possesses the vault_read skill."""
        skills = profile.get("skills") or []
        return "vault_read" in skills

    @staticmethod
    def _allowed_rel_prefixes(mv: str, allowed_dirs: list[str]) -> list[str]:
        """`allowed_dirs` as vault-relative "Foo/"-style prefixes; "" means the
        whole vault. For filtering the whole-vault manifest down to a persona's
        sandbox without touching disk."""
        out: list[str] = []
        mv_real = os.path.realpath(mv)
        for a in allowed_dirs:
            if os.path.realpath(a) == mv_real:
                return [""]
            out.append(os.path.relpath(a, mv).replace(os.sep, "/").rstrip("/") + "/")
        return out

    @classmethod
    def find_chronological_notes(cls, profile: dict[str, Any]) -> list[str]:
        """Dynamically discovers all chronological, daily, and journal notes across allowed vault folders."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return []

        # Manifest fast-path (ADR-078) — no filesystem walk when the map is live.
        manifest = cls.get_manifest()
        if manifest is not None:
            date_re = re.compile(
                r"^\d{4}-\d{2}-\d{2}\.(?:md|markdown|txt)$", re.IGNORECASE
            )
            prefixes = cls._allowed_rel_prefixes(mv, allowed_dirs)
            hits: list[str] = []
            for n in manifest.get("nodes", []):
                rel = str(n.get("rel_path", "")).replace(os.sep, "/")
                if (
                    not n.get("exists")
                    or not rel.endswith((".md", ".markdown", ".txt"))
                    or rel.endswith(".excalidraw.md")
                ):
                    continue
                if not any(p == "" or rel.startswith(p) for p in prefixes):
                    continue
                folder_low = os.path.dirname(rel).lower()
                if (
                    date_re.match(os.path.basename(rel))
                    or "daily" in folder_low
                    or "journal" in folder_low
                    or "diary" in folder_low
                ):
                    hits.append(os.path.join(mv, n["rel_path"]))
            return hits

        raw_ignore = config_manager.get("vault.ignore_folders") or [
            ".obsidian",
            ".git",
            "Attachments",
            ".trash",
            "Drawings",
        ]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}\.(?:md|markdown|txt)$")

        results: list[str] = []
        for allowed in allowed_dirs:
            if not os.path.exists(allowed):
                continue
            for root, dirs, files in os.walk(allowed):
                dirs[:] = [
                    d
                    for d in dirs
                    if not d.startswith(".") and d.lower() not in ignore_dirs
                ]
                for fn in files:
                    if fn.endswith((".md", ".markdown", ".txt")) and not fn.endswith(
                        ".excalidraw.md"
                    ):
                        fp = os.path.join(root, fn)
                        if is_safe_path(fp, allowed):
                            if (
                                date_pattern.match(fn)
                                or "daily" in root.lower()
                                or "journal" in root.lower()
                                or "diary" in root.lower()
                            ):
                                results.append(fp)
        return results

    @classmethod
    def get_discovered_folders(cls, profile: dict[str, Any]) -> dict[str, str]:
        """Discovers real directory names and their full paths dynamically across allowed vault folders."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return {}

        # Manifest fast-path (ADR-078) — immediate child folders of each allowed
        # dir straight from the map's folder index, no scandir.
        manifest = cls.get_manifest()
        if manifest is not None:
            folder_keys = list(manifest.get("folders", {}).keys())
            discovered = {}
            mv_real = os.path.realpath(mv)
            for allowed in allowed_dirs:
                scoped = os.path.realpath(allowed) != mv_real
                prefix = (
                    (
                        os.path.relpath(allowed, mv).replace(os.sep, "/").rstrip("/")
                        + "/"
                    )
                    if scoped
                    else ""
                )
                if scoped:
                    discovered[os.path.basename(allowed).lower()] = allowed
                for key in folder_keys:
                    k = key.replace(os.sep, "/")
                    if prefix and not k.startswith(prefix):
                        continue
                    rest = k[len(prefix) :]
                    if rest and "/" not in rest:  # immediate child only
                        discovered[rest.lower()] = os.path.join(mv, key)
            return discovered

        raw_ignore = config_manager.get("vault.ignore_folders") or [
            ".obsidian",
            ".git",
            "Attachments",
            ".trash",
            "Drawings",
        ]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        discovered: dict[str, str] = {}

        for allowed in allowed_dirs:
            if not os.path.exists(allowed):
                continue
            if allowed != mv:
                discovered[os.path.basename(allowed).lower()] = allowed
            try:
                for entry in os.scandir(allowed):
                    if (
                        entry.is_dir()
                        and not entry.name.startswith(".")
                        and entry.name.lower() not in ignore_dirs
                    ):
                        discovered[entry.name.lower()] = entry.path
            except Exception as e:
                log.debug("Failed to scan %s for sub-vaults: %s", allowed, e)
        return discovered

    @classmethod
    def _recall_hit(
        cls,
        profile: dict[str, Any],
        cand: str,
        target_folder: str | None = None,
        require_confident: bool = False,
    ) -> str | None:
        """Search one candidate term for the conversational-recall fallback.
        A single result — or a clear title match on the first hit — returns the
        note's *full verbatim body* (the strongest possible grounding payload);
        anything broader returns the ranked digest so the model can pick.

        `require_confident` drops that digest fallback entirely: the caller
        passes it for `_recall_candidates`' *decomposed single-token* tries
        (a multi-word phrase whittled down to its longest leftover words),
        never for the original phrase itself. Live bug: "play our favorite
        game" (no folder-scoped match) decomposed to the single word
        "favorite", which matched five unrelated notes' body text and was
        accepted as a digest anyway - a common English word loosely
        appearing in several notes isn't the same evidence as the user's own
        multi-word phrase matching broadly; only a strong single/title match
        earns trust once the subject has been cut down to one bare word."""
        results = cls.search_structured(profile, cand, target_folder=target_folder)
        if not results:
            return None
        top = results[0]
        if len(results) == 1 or top.get("match_type") == "title":
            body = cls.read_note(
                profile, top.get("rel_path") or top.get("file_name", "")
            )
            if body and not body.startswith(("⚠️", "Error reading", "Note `")):
                loc = f" in `{target_folder}/`" if target_folder else ""
                return (
                    f"### Ground-Truth Sandboxed Vault Note (`{top.get('rel_path')}` "
                    f"— Exact Content, matched '{cand}'{loc}):\n{body[:3500]}"
                )
        if require_confident:
            return None
        digest = cls.format_search_digest(cand, results)
        loc = f" in `{target_folder}/`" if target_folder else ""
        return f"### Ground-Truth Vault Search Results for '{cand}'{loc}:\n{digest}"

    # Matches the label on a single-file "Ground-Truth ... Exact Content" block
    # built by resolve_turn_context below. Used only to re-read that same note
    # fresh before reusing it on a later turn — see refresh_note_context.
    _SANDBOXED_NOTE_RE = re.compile(
        r"^### Ground-Truth Sandboxed Vault Note \(`([^`]+)` - Exact Content\):\n"
    )

    @classmethod
    def refresh_note_context(cls, profile: dict[str, Any], cached_text: str) -> str:
        """Re-reads a cached single-note vault context from disk before reuse
        on a later turn. `active_vault_ctx` in the engine carries a resolved
        context forward across turns that don't themselves trigger a fresh
        recall — but the note may have been edited since it was first read,
        and replaying the frozen text would silently contradict the
        "Ground-Truth"/"Exact Content" label it carries. Falls back to the
        cached text unchanged for anything that isn't a single-note read
        (manifest/backlink/search digests span multiple notes and are lower
        risk) or if the re-read fails."""
        m = cls._SANDBOXED_NOTE_RE.match(cached_text)
        if not m:
            return cached_text
        note_ref = m.group(1)
        fresh = cls.read_note(profile, note_ref)
        if not fresh or fresh.startswith("Note `") or fresh.startswith("⚠️") or fresh.startswith("Error reading"):
            return cached_text
        return f"### Ground-Truth Sandboxed Vault Note (`{note_ref}` - Exact Content):\n{fresh}"

    @classmethod
    def resolve_turn_context(cls, profile: dict[str, Any], message: str) -> str | None:
        """Skill-gated, structure-agnostic pre-inference retrieval conforming to skills/vault_read."""
        # 1. Skill Permission Gate: only proceed if persona is authorized for vault recall
        if not cls.has_vault_skill(profile):
            return None

        msg = message.strip()
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return None

        # 1b. Vault structure map (ADR-078). Any "how big / how organised / how
        #     many / what's in / stats" question about the vault gets the
        #     disk-true map — cheap, always accurate, no walk. Skipped when the
        #     message names a subject (that's a search, not a shape question).
        #     Inert unless `vault.manifest.enabled`; structure only.
        if (
            re.search(
                r"\b(vault|obsidian|journal|(?:my|our|the)\s+notes?)\b",
                msg,
                re.IGNORECASE,
            )
            and re.search(
                r"\b(structure|structured|organi[sz]\w+|hierarch\w+|layout|"
                r"topolog\w+|folders?|sub-?folders?|breakdown|stats?|status|"
                r"summary|overview|snapshot|inventory|shape|size|"
                r"how many|how much|how big|how large|how'?s|hows|"
                r"what'?s in|state of|count)\b",
                msg,
                re.IGNORECASE,
            )
            and not re.search(r"\babout\b|\bregarding\b|[\"'][^\"']{2,}[\"']", msg)
        ):
            manifest = cls.get_manifest()
            if manifest and manifest.get("nodes"):
                return cls.format_manifest_digest(manifest)

        # 2. Wikilink & Backlink Queries ("what notes link to [[OAuth]]?", "backlinks for Architecture")
        bl_match = re.search(
            r"(?:what\s+(?:notes\s+)?(?:link\s+to|reference)|who\s+(?:links\s+to|references)|backlinks?\s+(?:for|to|of)?)\s+(?:\[\[)?([a-zA-Z0-9_\-\s/\.]+?)(?:\]\])?(?:\?|$|\.|\n)",
            msg,
            re.IGNORECASE,
        )
        if bl_match:
            bl_target = bl_match.group(1).strip()
            if len(bl_target) >= 2:
                digest = cls.get_backlinks_digest(profile, bl_target)
                if digest and not digest.startswith("No backlinks found"):
                    return f"### Ground-Truth Vault Backlink Index for `[[{bl_target}]]`:\n{digest}"

        # 3. Quoted note title lookup (e.g. "If I Stay", 'If I Stay')
        for q_match in re.findall(r"[\"']([^\"']+)[\"']", msg):
            q_clean = q_match.strip()
            if len(q_clean) >= 2:
                content = cls.read_note(profile, q_clean)
                if (
                    content
                    and not content.startswith("Note `")
                    and not content.startswith("⚠️")
                ):
                    return f"### Ground-Truth Sandboxed Vault Note (`{q_clean}` - Exact Content):\n{content}"

        # 4. Explicit note reading requests ("read note X", "look at note X")
        rd = re.search(
            r"(?:read|open|check|look\s+at|show\s+me)\s+(?:the\s+)?note\s+([a-zA-Z0-9_\-/\.\s]+(?:\.md|\.markdown|\.txt|[a-zA-Z0-9]))",
            msg,
            re.IGNORECASE,
        )
        if rd:
            note_target = rd.group(1).strip()
            c = cls.read_note(profile, note_target)
            if c and not c.startswith("Note `") and not c.startswith("⚠️"):
                return f"### Ground-Truth Sandboxed Vault Note (`{note_target}` - Exact Content):\n{c}"

        # Subject of a conversational recall request ("Dylan's people entry" ->
        # "dylan people"), extracted once: it both gates the random sampler
        # below (a named subject is never a request for a *random* note) and
        # drives the case-8 fallback search.
        subject, had_leadin = cls._extract_recall_subject(msg)
        # A low-confidence guess (no explicit lead-in) shorter than a real
        # search term is noise, not a target — live bug: "g?" (shorthand for
        # "go") survived stopword-trimming as the winning fallback clause and
        # blocked the random-sample path below just as effectively as a
        # whole invented topic would have. Case 8 already required length
        # >= 3 for its own fallback search; applying that same bar here too
        # closes the same gap for the gates above it.
        if subject and not had_leadin and len(subject) < 3:
            subject = ""

        # 5. Chronological & Daily Journal Intent (Structure-Agnostic)
        is_chrono_query = bool(
            re.search(
                r"\b(daily|journal|diary|reflection|reflections|log|logs|day's\s+note|entry|entries)\b",
                msg,
                re.IGNORECASE,
            )
        )
        # Only an *explicit* ask for an arbitrary note — "pull"/"grab"/"get"/
        # "pick" alone are not it ("pull up Dylan's entry" names a target).
        sample_match = re.search(
            r"\b(?:random(?:ly)?|randam|rnd|surprise\s+me|a\s+random|any\s+(?:random\s+)?(?:one|note|entry|day)|"
            r"some\s+(?:random\s+)?(?:note|entry|day)|(?:pick|choose|grab|pull\s+up|show|give)\s+(?:me\s+)?(?:a|an|one|any)\b|"
            r"one\s+of\s+(?:my|the|our)|whatever\s+comes\s+up)\b",
            msg,
            re.IGNORECASE,
        )
        is_sample_request = bool(sample_match)

        # A low-confidence subject guess (no explicit recall lead-in like
        # "pull up notes on X") that comes from an earlier sentence than the
        # one actually making the random-note ask is filler, not a named
        # target — live bug: "hmmm.. not really what I expected. It should
        # be a random note from the thoughts folder" guessed the subject
        # "hmmm" from the reflex-reaction opener, which then blocked the
        # random-sample path below and sent an unrelated word to a vault-wide
        # search instead. Checked by sentence co-occurrence rather than an
        # enumerable filler-word list, so it generalises to any interjection.
        # A confident lead-in match is never cleared this way even if the
        # message also happens to mention "random" elsewhere.
        if subject and not had_leadin and sample_match:
            request_sentence = next(
                (
                    s
                    for s in re.split(r"[.?!]+\s+", msg)
                    if sample_match.group(0).lower() in s.lower()
                ),
                "",
            )
            if subject not in request_sentence.lower():
                subject = ""

        if is_chrono_query and is_sample_request and not subject:
            chrono_notes = cls.find_chronological_notes(profile)
            if chrono_notes:
                import random

                selected_fp = random.choice(chrono_notes)
                rel = os.path.relpath(selected_fp, mv)
                try:
                    with open(selected_fp, "r", encoding="utf-8", errors="ignore") as f:
                        body = f.read().strip()
                    if body:
                        return f"### Ground-Truth Sandboxed Vault Note (`{rel}` - Exact Content):\n{body[:3000]}"
                except Exception as e:
                    log.debug(
                        "Failed to read sampled chronological note %s: %s", rel, e
                    )

        # 6. Year-based chronological queries ("2020 journal entry")
        yr = re.search(r"\b(201\d|202\d|19\d\d)\b", msg)
        if yr and is_chrono_query:
            res = cls.search(profile, yr.group(1))
            if (
                res
                and not res.startswith("No notes found")
                and "not configured" not in res
            ):
                return (
                    f"### Ground-Truth Vault Search Results for '{yr.group(1)}':\n{res}"
                )

        # 7. Dynamic Real-Directory Discovery & Sampling (Zero Hardcoding)
        discovered_dirs = cls.get_discovered_folders(profile)
        triggers = config_manager.get("vault.search_triggers") or [
            "vault",
            "note",
            "notes",
            "folder",
            "journal",
            "backlink",
            "backlinks",
            "search",
            "find",
            "lookup",
            "look up",
            "recall",
            "remind me",
            "pull up",
            "what did i write",
            "what did i say",
            "do i have",
            "do we have",
        ]
        has_intent = any(k in msg.lower() for k in triggers)

        # Set when the message names a real folder case 7 below actually
        # tried and came up empty for - used to keep case 8 from then
        # re-broadening the same request to the whole vault (see there).
        folder_scope_matched = False

        if has_intent and discovered_dirs:
            for folder_name, folder_path in discovered_dirs.items():
                f_stem = folder_name.rstrip("s")
                if re.search(rf"\b{re.escape(f_stem)}\w*\b", msg, re.IGNORECASE):
                    folder_scope_matched = True
                    if is_sample_request and not subject:
                        samples = cls.get_random_sample_notes(
                            profile, folder_name, count=1
                        )
                        if samples:
                            return f"### Ground-Truth Selected Note from `{folder_name}/` (Exact Content):\n{samples}"
                    if re.search(
                        r"\b(scan|analyze|summarize|all|overview|connections?|access)\b",
                        msg,
                        re.IGNORECASE,
                    ):
                        return cls.get_folder_digest(profile, folder_name)
                    # A named subject alongside the folder ("Dylan's People entry")
                    # means search *that* inside the folder, not list the folder.
                    # A named subject alongside the folder ("Dylan's People entry")
                    # means search *that* inside the folder, not list the folder.
                    if subject:
                        for i, st in enumerate(
                            cls._recall_candidates(subject, drop=f_stem)
                        ):
                            hit = cls._recall_hit(
                                profile,
                                st,
                                target_folder=folder_name,
                                require_confident=i > 0,
                            )
                            if hit:
                                return hit
                    res = cls.search(profile, folder_name, target_folder=folder_name)
                    if (
                        res
                        and not res.startswith("No notes found")
                        and "not configured" not in res
                    ):
                        return f"### Ground-Truth Vault Search Results for '{folder_name}':\n{res}"

        # 8. Conversational recall fallback — search the extracted subject,
        #    retrying progressively narrower so a multi-word phrase that
        #    substring-matches nothing still surfaces its salient notes.
        #    Skipped when the message already named a real folder (case 7
        #    just tried it, scoped, and found nothing confident there) -
        #    live bug: re-running the same decomposed candidates unscoped
        #    let "bored" (from "I'm bored, let's play...") match an
        #    unrelated Quotes/ note vault-wide, silently dropping the
        #    folder the user actually asked for.
        if (
            (has_intent or had_leadin)
            and subject
            and len(subject) >= 3
            and not folder_scope_matched
        ):
            for i, cand in enumerate(cls._recall_candidates(subject)):
                hit = cls._recall_hit(profile, cand, require_confident=i > 0)
                if hit:
                    return hit

        return None

    @classmethod
    def _recall_candidates(cls, subject: str, drop: str = "") -> list[str]:
        """Ordered search terms for a recall subject: the full phrase first, then
        its most-specific single tokens (longest, then earliest), then the
        de-pluralised stem of each so an apostrophe-less possessive ('dylans' ->
        'dylan') still matches. `drop` removes one token (e.g. the folder name)."""
        return vault_recall.recall_candidates(subject, drop)
