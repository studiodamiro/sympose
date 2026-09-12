"""
Sandboxed Vault & Markdown Note Manager for Sympose.
"""

import os, re, datetime, logging
import yaml
from typing import Dict, Any, Optional, List, Tuple
from collections import defaultdict
from sympose.config import is_safe_path, config_manager
from sympose import vault_index, vault_manifest, vault_tree, vault_trash

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Backlink index cache — avoids a full vault walk on every message
# Key: tuple of allowed_dirs paths → (combined_mtime, index_dict)
# ---------------------------------------------------------------------------
_BACKLINK_CACHE: Dict[Tuple[str, ...], Tuple[float, Dict[str, List[Dict[str, Any]]]]] = {}

# ---------------------------------------------------------------------------
# Vault content snapshot cache — avoids re-walking + re-reading every note on
# every search_structured() / get_folder_digest() call. Same mtime-keyed
# invalidation strategy as _BACKLINK_CACHE.
# Key: tuple of scanned dir paths → (combined_mtime, flat list of parsed notes)
# ---------------------------------------------------------------------------
_VAULT_SNAPSHOT_CACHE: Dict[Tuple[str, ...], Tuple[float, List[Dict[str, Any]]]] = {}


def _dirs_mtime(dirs: List[str]) -> float:
    """Shallow top-level mtime watermark shared by the backlink index and the
    vault snapshot cache — matches the invalidation granularity already
    accepted by _BACKLINK_CACHE (touches to a direct child dir invalidate;
    a write several levels deep only bubbles up as far as its immediate
    parent's mtime, same as before)."""
    mtime = 0.0
    for d in dirs:
        try:
            mtime = max(mtime, os.path.getmtime(d))
        except OSError:
            pass
    return mtime



class VaultManager:
    """Manages sandboxed reading, writing, high-density manifests, and searching in Obsidian vaults."""

    # Lead-in phrases that precede the real subject of a conversational recall
    # request. Longest-first so multi-word forms strip before their prefixes.
    _RECALL_LEADINS: Tuple[str, ...] = (
        "what have i written about", "what did i write about", "what did i say about",
        "what do i have on", "what do i have about", "what did i write", "what did i say",
        "do i have any notes about", "do i have any notes on", "do i have notes about",
        "do i have notes on", "do i have a note about", "do i have anything about",
        "do we have any notes about", "do we have notes on", "do we have anything about",
        "remind me about", "remind me of", "tell me about", "recall our", "recall my",
        "search for", "look for", "look up", "look at", "check for", "dig up", "dig out",
        "pull up", "pull out", "bring up", "show me", "find me", "get me",
        "how about", "what about", "anything about", "anything on",
        "my notes about", "my notes on", "notes about", "notes on", "note about", "note on",
        "my journal about", "journal entry about", "journal about", "journal on",
        "remind me", "recall", "remember when", "remember",
    )
    # Politeness / modal wrappers that sit in front of a recall lead-in
    # ("can you pull up …", "please remind me …"). Stripped before the lead-in
    # scan but — unlike a lead-in — not themselves treated as recall intent.
    _RECALL_WRAPPERS: Tuple[str, ...] = (
        "can you please", "could you please", "would you please", "can you kindly",
        "i want you to", "i'd like you to", "i would like you to", "i need you to",
        "can you", "could you", "would you", "will you", "can we", "could we",
        "can u", "cud u", "lets", "let's", "let us", "help me", "go ahead and",
        "please", "kindly", "pls", "plz",
    )
    # Tokens with no value as a substring search term; trimmed from both ends of
    # an extracted subject.
    _SUBJECT_STOPWORDS: frozenset = frozenset({
        "the", "a", "an", "my", "our", "your", "some", "any", "that", "this", "these",
        "up", "on", "in", "of", "for", "about", "regarding", "re", "from", "with",
        "please", "just", "also", "again", "vault", "obsidian", "note", "notes",
        "journal", "journals", "diary", "entry", "entries", "reflection", "reflections",
        "log", "logs", "did", "do", "i", "we", "you", "have", "had", "has",
        "write", "wrote", "written", "say", "said", "anything", "something", "stuff",
        "thing", "things", "please", "and", "or", "me", "us",
        # sample / chrono filler — a "subject" made only of these is no subject
        "random", "randomly", "randam", "surprise", "whatever", "arbitrary",
        "daily", "recent", "latest", "old", "past",
        # stray retrieval verbs that can leak past the lead-in scan
        "grab", "get", "fetch", "pull", "bring", "show", "give", "pick", "choose",
    })

    @staticmethod
    def _extract_recall_subject(message: str) -> Tuple[str, bool]:
        """Best-effort extraction of the *subject* of a conversational recall
        request: 'pull up my notes on Rilke' -> 'rilke', 'what did I write about
        grief in my journal' -> 'grief'. Substring search needs a tight phrase;
        the whole lead-in-plus-subject string matches nothing. Returns
        (subject, had_leadin) — had_leadin is True when a recall phrasing
        ('tell me about', 'pull up', …) was consumed, which is itself a signal
        of vault intent even absent a trigger keyword."""
        raw = message.strip().strip("?.!").lower()
        raw = re.sub(r"^(?:hey|hi|hello|yo|good\s+\w+)[\s,]+(?:\w+[\s,]+)?", "", raw).strip()
        # Possessive → bare stem so a substring search on "dylans" / "dylan's"
        # still matches the note that only ever spells it "Dylan".
        raw = re.sub(r"(\w)['’]s\b", r"\1", raw)

        def _from_clause(q: str) -> Tuple[str, bool]:
            had_leadin = False
            changed = True
            while changed:
                changed = False
                for phrase in VaultManager._RECALL_WRAPPERS:
                    if q.startswith(phrase + " "):
                        q, changed = q[len(phrase):].strip(), True
                        break
                for phrase in VaultManager._RECALL_LEADINS:
                    if q.startswith(phrase + " "):
                        q, changed, had_leadin = q[len(phrase):].strip(), True, True
                        break
            m = re.search(r"\b(?:about|on|regarding|mentioning|discussing|concerning)\s+(.+)$", q)
            if m:
                q = m.group(1).strip()
            q = re.sub(
                r"\s+(?:in|from|within|inside)\s+(?:my|our|the\s+)?\s*"
                r"(?:journal|diary|vault|notes?|daily|entries|reflections?|logs?)\b.*$",
                "", q,
            ).strip()
            # A recall request rarely spans a conjunction ("… and see if my
            # memory's right"); keep only the head clause.
            q = re.split(r"\s+(?:and|but|so|then)\s+", q, maxsplit=1)[0].strip()
            toks = [t for t in re.split(r"\s+", q) if t]
            while toks and toks[0] in VaultManager._SUBJECT_STOPWORDS:
                toks.pop(0)
            while toks and toks[-1] in VaultManager._SUBJECT_STOPWORDS:
                toks.pop()
            return " ".join(toks).strip(), had_leadin

        # "i wish i could do that. can you pull up X" — process each sentence and
        # prefer the one that actually carries a recall lead-in.
        clauses = [c.strip() for c in re.split(r"[.?!]+\s+", raw) if c.strip()] or [raw]
        best = ("", False)
        for c in clauses:
            subj, lead = _from_clause(c)
            if lead and subj:
                return subj, True
            if subj and not best[0]:
                best = (subj, lead)
        return best

    @classmethod
    def has_recall_intent(cls, message: str) -> bool:
        """True when the message is itself a fresh vault-recall request (a recall
        lead-in was consumed, or a configured search trigger appears). The engine
        uses this to decide *not* to reuse a previous turn's injected vault
        context when the current turn asked its own vault question and retrieval
        came back empty — answering a fresh 'pull up X' from a stale unrelated
        note is exactly the fabrication this guards against."""
        _, had_leadin = cls._extract_recall_subject(message)
        if had_leadin:
            return True
        triggers = config_manager.get("vault.search_triggers") or ["vault", "note", "notes", "journal", "recall"]
        return any(k in message.lower() for k in triggers)

    @staticmethod
    def _get_master_vault() -> Optional[str]:
        mv = os.getenv("MASTER_VAULT_PATH")
        return os.path.abspath(os.path.expanduser(mv)) if mv else None

    @classmethod
    def get_allowed_dirs(cls, profile: Dict[str, Any]) -> List[str]:
        mv = cls._get_master_vault()
        if not mv: return []
        try:
            os.makedirs(mv, exist_ok=True)
            folders = profile.get("vault_folders") or [profile.get("vault_folder", "")]
            if "" in folders or "*" in folders or "all" in folders: return [mv]
            allowed = []
            for f in folders:
                path = os.path.join(mv, f.strip()) if f.strip() else mv
                if is_safe_path(path, mv):
                    os.makedirs(path, exist_ok=True)
                    allowed.append(path)
            return allowed or [mv]
        except Exception:
            return []

    @classmethod
    def get_primary_dir(cls, profile: Dict[str, Any]) -> Optional[str]:
        dirs = cls.get_allowed_dirs(profile)
        return dirs[0] if dirs else None

    @classmethod
    def read_note(cls, profile: Dict[str, Any], note_name: str) -> str:
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs: return "⚠️ Master notes directory not configured or access denied."
        clean_name = note_name.strip().strip("\"'")
        if not clean_name.endswith(".md"): clean_name += ".md"

        direct_target = os.path.join(mv, clean_name)
        for allowed in allowed_dirs:
            if is_safe_path(direct_target, allowed) and os.path.exists(direct_target):
                try:
                    with open(direct_target, "r", encoding="utf-8", errors="ignore") as f:
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
        raw_ignore = config_manager.get("vault.ignore_folders") or [".obsidian", ".git", "Attachments", ".trash"]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        for allowed in allowed_dirs:
            for root, dirs, files in os.walk(allowed):
                dirs[:] = [d for d in dirs if d.lower() not in ignore_dirs and not d.startswith(".")]
                for fn in files:
                    if fn.endswith((".md", ".markdown", ".txt")):
                        if os.path.splitext(fn)[0].lower() == stem_target:
                            fp = os.path.join(root, fn)
                            if is_safe_path(fp, allowed):
                                try:
                                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                                        return f.read().strip()
                                except Exception as e:
                                    return f"Error reading note `{clean_name}`: {e}"

        return f"Note `{clean_name}` not found in allowed vault folders."

    @classmethod
    def get_folder_digest(cls, profile: Dict[str, Any], folder_name: str, max_files: int = 50) -> str:
        """Extracts high-density 1-line metadata for all notes in a folder for comprehensive synthesis."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs: return "⚠️ Master notes directory not configured or access denied."
        target_dir = next((d for d in allowed_dirs if os.path.basename(d).lower() == folder_name.lower()), None)
        if not target_dir:
            for d in allowed_dirs:
                candidate = os.path.join(d, folder_name)
                if os.path.exists(candidate) and is_safe_path(candidate, d):
                    target_dir = candidate
                    break
        if not target_dir or not os.path.exists(target_dir):
            return f"Folder `{folder_name}` not found in allowed vault directories."

        entries: List[str] = []
        for entry in cls._get_vault_snapshot(mv, [target_dir])[:max_files]:
            fn, head = entry["file_name"], entry["full_content"][:1000]
            parts = []
            for k in ("name", "title", "aka", "tags", "birthday", "created", "up", "author"):
                m = re.search(rf"^{k}:\s*([^\n\r]+)", head, re.M | re.I)
                if m and m.group(1).strip() and not m.group(1).strip().startswith(("-", "[")):
                    parts.append(f"{k.capitalize()}: {m.group(1).strip()}")
                else:
                    sub = re.findall(rf"^{k}:(?:\s*\n)((?:\s+-\s+[^\n]+\n)+)", head, re.M | re.I)
                    if sub:
                        items = [x.strip("- \t\n\"'") for x in sub[0].strip().split("\n")]
                        parts.append(f"{k.capitalize()}: {', '.join(items)}")
            fl = next((line.strip("# \t\r") for line in head.split("\n") if line.strip() and not line.startswith("---") and ":" not in line), "")
            summary = " | ".join(parts) if parts else fl[:80]
            entries.append(f"- `{fn}`: {summary}" if summary else f"- `{fn}`")

        return f"### High-Density Folder Digest (`{folder_name}/` - {len(entries)} notes):\n" + "\n".join(entries) if entries else f"No notes found in `{folder_name}/`."

    @classmethod
    def get_random_sample_notes(cls, profile: Dict[str, Any], folder_name: str, count: int = 2) -> str:
        """Extracts real note bodies from 1-3 randomly sampled notes in the folder so the model has true ground-truth content."""
        import random
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs: return "⚠️ Master notes directory not configured or access denied."
        target_dir = next((d for d in allowed_dirs if os.path.basename(d).lower() == folder_name.lower()), None)
        if not target_dir:
            for d in allowed_dirs:
                candidate = os.path.join(d, folder_name)
                if os.path.exists(candidate) and is_safe_path(candidate, d):
                    target_dir = candidate
                    break
        if not target_dir or not os.path.exists(target_dir):
            return ""

        raw_ignore = config_manager.get("vault.ignore_folders") or [".obsidian", ".git", "Attachments", ".trash"]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        valid_files = []
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d.lower() not in ignore_dirs and not d.startswith(".")]
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
                    payloads.append(f"### Ground-Truth Sandboxed Vault Note (`{rel}` - Exact Content):\n{body[:2500]}")
            except Exception:
                pass
        return "\n\n---\n\n".join(payloads)

    _last_searches: Dict[str, List[Dict[str, Any]]] = {}

    @staticmethod
    def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
        """Extracts YAML frontmatter dictionary and clean markdown body."""
        if not content.startswith("---"):
            return {}, content

        # Closing `---` may be the last line of the file (frontmatter-only note),
        # carry trailing spaces, or be followed by a body. All three are valid.
        match = re.match(r"^---\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n(.*))?\Z", content, re.DOTALL)
        if not match:
            return {}, content

        raw_yaml, body = match.group(1), match.group(2) or ""
        meta: Dict[str, Any] = {}
        try:
            parsed = yaml.safe_load(raw_yaml)
            if isinstance(parsed, dict):
                meta = parsed
        except Exception:
            pass

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
    def _get_vault_snapshot(cls, mv: str, dirs: List[str]) -> List[Dict[str, Any]]:
        """Returns a cached, flat list of every note under `dirs` (path, parsed
        frontmatter, body, raw content), rebuilt only when a dir's mtime changes.
        Shared by search_structured() and get_folder_digest() so neither has to
        re-walk + re-read the vault from disk on every call."""
        cache_key = tuple(sorted(dirs))
        current_mtime = _dirs_mtime(dirs)
        cached_mtime, cached_snapshot = _VAULT_SNAPSHOT_CACHE.get(cache_key, (0.0, []))
        if current_mtime == cached_mtime and cached_snapshot:
            return cached_snapshot

        raw_ignore = config_manager.get("vault.ignore_folders") or [".obsidian", ".git", "Attachments", ".trash"]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        snapshot: List[Dict[str, Any]] = []

        for allowed in dirs:
            if not os.path.exists(allowed):
                continue
            for root, subdirs, files in os.walk(allowed):
                subdirs[:] = [d for d in subdirs if d.lower() not in ignore_dirs and not d.startswith(".")]
                for file in sorted(files):
                    if not file.endswith((".md", ".markdown", ".txt")):
                        continue
                    file_path = os.path.join(root, file)
                    if not is_safe_path(file_path, allowed):
                        continue
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            full_content = f.read()
                    except Exception:
                        continue
                    meta, body = cls.parse_frontmatter(full_content)
                    snapshot.append({
                        "file_name": file,
                        "rel_path": os.path.relpath(file_path, mv),
                        "abs_path": file_path,
                        "full_content": full_content,
                        "meta": meta,
                        "body": body,
                    })

        _VAULT_SNAPSHOT_CACHE[cache_key] = (current_mtime, snapshot)
        return snapshot

    @staticmethod
    def _workspace_dir() -> str:
        return os.path.dirname(os.path.abspath(config_manager.config_path)) or "."

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
                cls._workspace_dir(), mv, os.path.relpath(target_file, mv),
                os.path.basename(target_file), meta, body,
            )
        except Exception:
            log.debug("[vault] incremental FTS reindex failed for %s", target_file, exc_info=True)

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
                cls._workspace_dir(), mv, os.path.relpath(target_file, mv), meta, full_content,
                ignore_folders=config_manager.get("vault.ignore_folders") or [],
            )
        except Exception:
            log.debug("[vault] manifest patch failed for %s", target_file, exc_info=True)

    @classmethod
    def get_manifest(cls) -> Optional[Dict[str, Any]]:
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
            cls._workspace_dir(), mv, lambda: cls._get_vault_snapshot(mv, [mv]),
            read_notes=lambda rels: cls._read_note_entries(mv, rels),
            ignore_folders=config_manager.get("vault.ignore_folders") or [],
            debounce=config_manager.get("vault.manifest.check_debounce_seconds"),
            max_nodes=config_manager.get("vault.manifest.max_nodes") or 0,
        )

    @classmethod
    def _read_note_entries(cls, mv: str, rel_paths: List[str]) -> List[Dict[str, Any]]:
        """Read + parse just these notes into `_get_vault_snapshot`-shaped
        entries — the reader the ADR-078.4 manifest delta hands to
        `vault_manifest.ensure_fresh` so an external edit re-parses only what
        changed, not the whole vault."""
        out: List[Dict[str, Any]] = []
        for rel in rel_paths:
            fp = os.path.join(mv, rel)
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    full_content = f.read()
            except OSError:
                continue
            meta, body = cls.parse_frontmatter(full_content)
            out.append({
                "file_name": os.path.basename(rel), "rel_path": rel.replace(os.sep, "/"),
                "abs_path": fp, "full_content": full_content, "meta": meta, "body": body,
            })
        return out

    @classmethod
    def get_vault_graph(cls) -> Dict[str, Any]:
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
        degree: Dict[str, int] = {}
        for l in links:
            degree[l["source"]] = degree.get(l["source"], 0) + 1
            degree[l["target"]] = degree.get(l["target"], 0) + 1
        def _label(n: Dict[str, Any]) -> str:
            raw = str(n.get("title") or n["id"]).strip()
            return raw if len(raw) <= 64 else raw[:63].rstrip() + "…"

        nodes = [
            {
                "id": n["id"], "label": _label(n), "folder": n["folder"],
                "tags": n.get("tags", []), "val": degree.get(n["id"], 0) + 1,
                "exists": n.get("exists", True),
            }
            for n in manifest.get("nodes", [])
        ]
        return {"nodes": nodes, "links": links}

    @classmethod
    def _list_real_folders(cls, mv: str, dirs: List[str]) -> List[str]:
        """Vault-relative paths of every real subdirectory under `dirs` — a
        directory-only walk (no file reads, same ignore list as
        `_get_vault_snapshot`) so `build_tree` can show a folder that exists
        on disk but holds no notes yet (ADR-098)."""
        raw_ignore = config_manager.get("vault.ignore_folders") or [".obsidian", ".git", "Attachments", ".trash"]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        seen: set = set()
        out: List[str] = []
        for base in dirs:
            if not os.path.exists(base):
                continue
            for root, subdirs, _ in os.walk(base):
                subdirs[:] = [d for d in subdirs if d.lower() not in ignore_dirs and not d.startswith(".")]
                for d in subdirs:
                    rel = os.path.relpath(os.path.join(root, d), mv).replace(os.sep, "/")
                    if rel not in seen:
                        seen.add(rel)
                        out.append(rel)
        return out

    @classmethod
    def get_vault_tree(cls, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
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
        prefixes: List[str] = []
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
        return vault_tree.build_tree(manifest.get("nodes", []), prefixes, real_folders)

    @classmethod
    def _search_fts(cls, mv: str, search_dirs: List[str], query_clean: str, max_results: int) -> Optional[List[Dict[str, Any]]]:
        """`sqlite_fts` search path (ADR-070.5). Returns None if the index isn't
        usable this run — the caller falls back to the `direct` walk below."""
        workspace_dir = cls._workspace_dir()
        fresh = vault_index.ensure_fresh(workspace_dir, mv, lambda: cls._get_vault_snapshot(mv, [mv]))
        if not fresh:
            return None
        rows = vault_index.query(workspace_dir, mv, query_clean, search_dirs, max_results)
        if rows is None:
            return None
        results = []
        for idx, r in enumerate(rows, start=1):
            results.append({
                "file_name": r["file_name"], "rel_path": r["rel_path"], "abs_path": os.path.join(mv, r["rel_path"]),
                "match_type": "content", "line_no": 1, "snippet": r["snippet"], "title": r["title"],
                "tags": [], "meta": {}, "index": idx,
            })
        return results

    @classmethod
    def search_structured(cls, profile: Dict[str, Any], query: str, target_folder: Optional[str] = None, max_results: int = 15) -> List[Dict[str, Any]]:
        """Performs fast sandboxed vault search returning structured match metadata with snippets."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return []

        search_dirs = [d for d in allowed_dirs if os.path.basename(d).lower() == target_folder.lower()] if target_folder else allowed_dirs
        search_dirs = search_dirs or allowed_dirs

        query_clean = query.lower().strip().strip("\"'")
        if not query_clean:
            return []

        if config_manager.get("vault.search_mode", "direct") == "sqlite_fts":
            fts_results = cls._search_fts(mv, search_dirs, query_clean, max_results)
            if fts_results is not None:
                handle_key = profile.get("handle", "default").lower()
                cls._last_searches[handle_key] = fts_results
                return fts_results
            # Index unusable this run (no FTS5, or a rebuild failure) — fall
            # through to `direct` below rather than return an empty result.

        title_matches: List[Dict[str, Any]] = []
        content_matches: List[Dict[str, Any]] = []

        try:
            for entry in cls._get_vault_snapshot(mv, search_dirs):
                file, rel_path, full_content, meta, body = (
                    entry["file_name"], entry["rel_path"], entry["full_content"], entry["meta"], entry["body"]
                )
                tags = meta.get("tags", [])
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.replace(",", " ").split() if t.strip()]
                elif not isinstance(tags, list):
                    tags = []

                is_title_match = (query_clean in file.lower() or query_clean in rel_path.lower())

                if is_title_match:
                    fl = next((line.strip("# \t\r") for line in body.splitlines() if line.strip() and not line.startswith("---") and ":" not in line), "")
                    clean_fl = " ".join(fl.split())
                    if len(clean_fl) > 70:
                        clean_fl = clean_fl[:67].rstrip() + "..."
                    title_matches.append({
                        "file_name": file,
                        "rel_path": rel_path,
                        "abs_path": entry["abs_path"],
                        "match_type": "title",
                        "line_no": 1,
                        "snippet": clean_fl or "Exact title match",
                        "title": meta.get("title") or meta.get("name") or os.path.splitext(file)[0],
                        "tags": tags,
                        "meta": meta,
                    })
                elif query_clean in full_content.lower():
                    matched_line_no = 1
                    matched_snippet = ""
                    for line_idx, line in enumerate(full_content.splitlines(), start=1):
                        if query_clean in line.lower():
                            matched_line_no = line_idx
                            clean_l = " ".join(line.strip().strip("#*-> ").split())
                            q_idx = clean_l.lower().find(query_clean)
                            if q_idx > 25:
                                clean_l = "..." + clean_l[max(q_idx - 15, 0):]
                            if len(clean_l) > 70:
                                clean_l = clean_l[:67].rstrip() + "..."
                            matched_snippet = clean_l
                            break
                    content_matches.append({
                        "file_name": file,
                        "rel_path": rel_path,
                        "abs_path": entry["abs_path"],
                        "match_type": "content",
                        "line_no": matched_line_no,
                        "snippet": matched_snippet or f"Match found on line {matched_line_no}",
                        "title": meta.get("title") or meta.get("name") or os.path.splitext(file)[0],
                        "tags": tags,
                        "meta": meta,
                    })

                if len(title_matches) + len(content_matches) >= max_results * 2:
                    break
        except Exception:
            pass

        all_results = (title_matches + content_matches)[:max_results]
        for idx, res in enumerate(all_results, start=1):
            res["index"] = idx

        # Keyed strictly per-persona — no shared fallback key. A shared key meant
        # persona A's search results could leak into persona B's `/read <n>` if B
        # hadn't searched yet in the same process (two Slack threads on different
        # personas, or two CLI runs sharing a workspace).
        handle_key = profile.get("handle", "default").lower()
        cls._last_searches[handle_key] = all_results
        return all_results

    @classmethod
    def get_last_search(cls, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Returns the most recent search results for the given profile."""
        handle_key = profile.get("handle", "default").lower()
        return cls._last_searches.get(handle_key, [])

    @classmethod
    def format_search_digest(cls, query: str, results: List[Dict[str, Any]]) -> str:
        """Formats structured search results into a clean, high-density Markdown list."""
        if not results:
            return f"No notes found matching `{query}` in allowed vault folders."

        lines = [f"### 🔍 Vault Search: \"{query}\" ({len(results)} note{'s' if len(results) != 1 else ''} found):\n"]
        for r in results:
            idx = r.get("index", 1)
            rel = r.get("rel_path", r.get("file_name", "note.md"))
            mtype = r.get("match_type", "content")
            line_no = r.get("line_no", 1)
            snippet = r.get("snippet", "")
            tags = r.get("tags", [])
            tag_str = f" `[{' '.join('#' + t.lstrip('#') for t in tags[:3])}]`" if tags else ""

            type_label = "*(Title Match)*" if mtype == "title" else f"*(Line {line_no})*"
            lines.append(f"**[{idx}] `{rel}`** {type_label}{tag_str}")
            if snippet:
                lines.append(f"  > {snippet}")
            lines.append("")

        lines.append("──────────────────────────────────────────────────────────────────────────")
        lines.append("*Quick Nav: `/read <#>` to view in terminal | `/open <#>` to open in Obsidian | `/vault back` to return*")
        return "\n".join(lines)

    @classmethod
    def search(cls, profile: Dict[str, Any], query: str, target_folder: Optional[str] = None) -> str:
        results = cls.search_structured(profile, query, target_folder=target_folder)
        return cls.format_search_digest(query, results)

    @classmethod
    def resolve_note_target(cls, profile: Dict[str, Any], target: str) -> Tuple[Optional[str], Optional[str]]:
        """Resolves target string (index number, relative path, or filename) to (rel_path, abs_path)."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return None, None

        clean_target = target.strip().strip("\"'")
        handle_key = profile.get("handle", "default").lower()
        cached = cls._last_searches.get(handle_key, [])

        # 1. Number shortcut [1-N]
        if clean_target.isdigit():
            idx = int(clean_target)
            for item in cached:
                if item.get("index") == idx:
                    return item.get("rel_path"), item.get("abs_path")

        # 2. Match exact rel_path or stem in cached results
        t_stem = os.path.splitext(os.path.basename(clean_target))[0].lower()
        for item in cached:
            if item.get("rel_path", "").lower() == clean_target.lower() or os.path.splitext(item.get("file_name", ""))[0].lower() == t_stem:
                return item.get("rel_path"), item.get("abs_path")

        # 3. Direct lookup in vault
        target_name = clean_target if clean_target.endswith((".md", ".txt")) else clean_target + ".md"
        direct_target = os.path.join(mv, target_name)
        for allowed in allowed_dirs:
            if is_safe_path(direct_target, allowed) and os.path.exists(direct_target):
                return os.path.relpath(direct_target, mv), direct_target

        for allowed in allowed_dirs:
            candidate = os.path.join(allowed, os.path.basename(target_name))
            if is_safe_path(candidate, allowed) and os.path.exists(candidate):
                return os.path.relpath(candidate, mv), candidate

        # 4. Recursive lookup in allowed dirs
        raw_ignore = config_manager.get("vault.ignore_folders") or [".obsidian", ".git", "Attachments", ".trash"]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        for allowed in allowed_dirs:
            for root, dirs, files in os.walk(allowed):
                dirs[:] = [d for d in dirs if d.lower() not in ignore_dirs and not d.startswith(".")]
                for fn in files:
                    if os.path.splitext(fn)[0].lower() == t_stem:
                        fp = os.path.join(root, fn)
                        if is_safe_path(fp, allowed):
                            return os.path.relpath(fp, mv), fp

        return None, None

    @classmethod
    def open_in_obsidian(cls, profile: Dict[str, Any], target: str) -> Tuple[bool, str]:
        """Opens note in Obsidian desktop app / system default editor."""
        import subprocess, platform
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

    @staticmethod
    def extract_wikilinks(content: str) -> List[Dict[str, Any]]:
        """Extracts structured wikilink metadata from text content, supporting aliases and heading anchors."""
        pattern = re.compile(r"\[\[([^\]\|#]+)(?:#([^\]\|]+))?(?:\|([^\]]+))?\]\]")
        links = []
        for match in pattern.finditer(content):
            target = match.group(1).strip()
            heading = match.group(2).strip() if match.group(2) else None
            alias = match.group(3).strip() if match.group(3) else None
            stem = os.path.splitext(os.path.basename(target))[0].lower().strip()
            links.append({
                "target": target,
                "stem": stem,
                "heading": heading,
                "alias": alias,
                "raw": match.group(0),
            })
        return links

    @classmethod
    def get_forward_links(cls, profile: Dict[str, Any], note_name: str) -> List[Dict[str, Any]]:
        """Extracts all outgoing wikilinks from a given note within allowed vault folders."""
        content = cls.read_note(profile, note_name)
        if not content or content.startswith("Note `") or content.startswith("⚠️"):
            return []
        return cls.extract_wikilinks(content)

    @classmethod
    def build_backlink_index(cls, profile: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Constructs an inverted backlink index, using a mtime cache to skip re-walks on unchanged vaults."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return {}

        cache_key = tuple(sorted(allowed_dirs))
        current_mtime = _dirs_mtime(allowed_dirs)
        cached_mtime, cached_index = _BACKLINK_CACHE.get(cache_key, (0.0, {}))
        if current_mtime == cached_mtime and cached_index:
            return cached_index

        inverted_index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        raw_ignore = config_manager.get("vault.ignore_folders") or [".obsidian", ".git", "Attachments", ".trash"]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        pattern = re.compile(r"\[\[([^\]\|#]+)(?:#([^\]\|]+))?(?:\|([^\]]+))?\]\]")

        try:
            for allowed in allowed_dirs:
                if not os.path.exists(allowed):
                    continue
                for root, dirs, files in os.walk(allowed):
                    dirs[:] = [d for d in dirs if d.lower() not in ignore_dirs and not d.startswith(".")]
                    for fn in sorted(files):
                        if fn.endswith((".md", ".markdown", ".txt")):
                            fp = os.path.join(root, fn)
                            if not is_safe_path(fp, allowed):
                                continue
                            rel_path = os.path.relpath(fp, mv)
                            try:
                                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                                    for line_idx, line in enumerate(f, start=1):
                                        for match in pattern.finditer(line):
                                            target = match.group(1).strip()
                                            heading = match.group(2).strip() if match.group(2) else None
                                            alias = match.group(3).strip() if match.group(3) else None
                                            stem = os.path.splitext(os.path.basename(target))[0].lower().strip()
                                            inverted_index[stem].append({
                                                "source_file": fn,
                                                "rel_path": rel_path,
                                                "target": target,
                                                "target_stem": stem,
                                                "heading": heading,
                                                "alias": alias,
                                                "line_no": line_idx,
                                                "context_snippet": line.strip(),
                                            })
                            except Exception:
                                pass
        except Exception:
            pass

        result = dict(inverted_index)
        _BACKLINK_CACHE[cache_key] = (current_mtime, result)
        return result

    @classmethod
    def get_backlinks(cls, profile: Dict[str, Any], note_name: str) -> List[Dict[str, Any]]:
        """Queries the in-memory inverted index for all incoming references to note_name."""
        clean_target = note_name.strip().strip("\"'").replace("[[", "").replace("]]", "")
        stem = os.path.splitext(os.path.basename(clean_target))[0].lower().strip()
        index = cls.build_backlink_index(profile)
        return index.get(stem, [])

    @classmethod
    def get_backlinks_digest(cls, profile: Dict[str, Any], note_name: str, max_entries: int = 15) -> str:
        """Generates a high-density Markdown summary of backlinks for note_name."""
        clean_target = note_name.strip().strip("\"'").replace("[[", "").replace("]]", "")
        stem = os.path.splitext(os.path.basename(clean_target))[0].lower().strip()
        backlinks = cls.get_backlinks(profile, clean_target)
        if not backlinks:
            return f"No backlinks found referencing `[[{clean_target}]]` in allowed vault folders."

        lines = [f"### ◀ Backlinks for `[[{clean_target}]]` ({len(backlinks)} reference(s) found):"]
        for b in backlinks[:max_entries]:
            rel = b.get("rel_path", b.get("source_file", "unknown"))
            line_no = b.get("line_no", "")
            line_str = f" (Line {line_no})" if line_no else ""
            ctx = b.get("context_snippet", "")
            if ctx:
                lines.append(f"- **`{rel}`**{line_str}:\n  > {ctx[:200]}")
            else:
                lines.append(f"- **`{rel}`**{line_str}")

        if len(backlinks) > max_entries:
            lines.append(f"\n*(+ {len(backlinks) - max_entries} more references in vault)*")

        return "\n".join(lines)

    @staticmethod
    def format_manifest_digest(manifest: Dict[str, Any], max_folders: int = 30,
                               max_tags: int = 12, max_hubs: int = 8) -> str:
        """Compact, disk-true structural map from an ADR-078 manifest — folder
        counts, top tags, most-linked notes, unresolved links. Structure only:
        no note text, so it says *where* to look, never *what a note says*."""
        nodes = manifest.get("nodes", [])
        real = [n for n in nodes if n.get("exists")]
        real_ids = {n["id"] for n in real}
        top = sorted(((k, v) for k, v in manifest.get("folders", {}).items() if "/" not in k),
                     key=lambda kv: -kv[1])
        folder_lines = [f"- `{k}/` — {v} note{'s' if v != 1 else ''}" for k, v in top[:max_folders]] or ["- *(flat vault — no folders)*"]

        tag_counts: Dict[str, int] = {}
        inbound: Dict[str, int] = {}
        for n in real:
            for t in n.get("tags", []):
                tag_counts[t] = tag_counts.get(t, 0) + 1
        for l in manifest.get("links", []):
            if l["target"] in real_ids:
                inbound[l["target"]] = inbound.get(l["target"], 0) + 1
        tag_line = ", ".join(f"#{t} ({c})" for t, c in sorted(tag_counts.items(), key=lambda kv: -kv[1])[:max_tags]) or "—"
        hub_line = ", ".join(f"[[{h}]] ({c})" for h, c in sorted(inbound.items(), key=lambda kv: -kv[1])[:max_hubs]) or "—"

        out = [
            f"### Ground-Truth Vault Structure Map ({len(real)} notes, {len(top)} top-level folders)",
            "", "**Folders:**", *folder_lines, "",
            f"**Top tags:** {tag_line}",
            f"**Most-linked notes:** {hub_line}",
        ]
        ghosts = [n["id"] for n in nodes if not n.get("exists")]
        if ghosts:
            sample = ", ".join(f"[[{g}]]" for g in ghosts[:6])
            out.append(f"**Unresolved links:** {len(ghosts)} ({sample}{', …' if len(ghosts) > 6 else ''})")
        out.append("\n*Structure only — read the actual note for its contents.*")
        return "\n".join(out)

    @classmethod
    def get_template_for_path(cls, mv: str, note_name: str) -> Optional[str]:
        """Resolves the user's authentic Obsidian template from Templates/ folder if present."""
        if not mv or not os.path.exists(os.path.join(mv, "Templates")):
            return None

        tmpl_dir = os.path.join(mv, "Templates")
        norm = note_name.lower().replace("\\", "/")

        mapping = {
            "daily/": "Daily template.md",
            "thoughts/": "Thoughts template.md",
            "people/": "People template.md",
            "movies/": "Movie template.md",
            "quotes/": "Quote template.md",
        }

        matched_file = None
        for prefix, tmpl_name in mapping.items():
            if norm.startswith(prefix):
                matched_file = os.path.join(tmpl_dir, tmpl_name)
                break

        if not matched_file or not os.path.exists(matched_file):
            matched_file = os.path.join(tmpl_dir, "Note template.md")

        if os.path.exists(matched_file):
            try:
                with open(matched_file, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
        return None

    @classmethod
    def write_note(cls, profile: Dict[str, Any], note_name: str, content: str) -> str:
        mv, allowed_dirs, primary_dir = cls._get_master_vault(), cls.get_allowed_dirs(profile), cls.get_primary_dir(profile)
        if not mv or not primary_dir: return "Warning: Master notes directory not configured or path denied."
        if not (note_name.endswith(".md") or note_name.endswith(".canvas")):
            note_name += ".md"
        target_file = os.path.join(mv, note_name) if ("/" in note_name or "\\" in note_name) else os.path.join(primary_dir, note_name)
        if not any(is_safe_path(target_file, allowed) for allowed in allowed_dirs):
            return f"Security Error: Target path `{note_name}` is outside assigned sandbox."

        now = datetime.datetime.now()
        date_str, time_str, rel_display = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d %H:%M"), os.path.relpath(target_file, mv)
        clean_content = content.strip()

        try:
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            # If model already provided YAML frontmatter, write clean content directly
            if clean_content.startswith("---"):
                final_content = clean_content + "\n"
            else:
                title_heading = os.path.splitext(os.path.basename(note_name))[0].replace("_", " ").title()
                raw_tmpl = cls.get_template_for_path(mv, note_name)
                if raw_tmpl and raw_tmpl.strip().startswith("---"):
                    rendered_tmpl = (
                        raw_tmpl.replace("{{date}}", date_str)
                        .replace("{{time}}", time_str)
                        .replace("{{title}}", title_heading)
                        .replace("{{date:YYYY}}", now.strftime("%Y"))
                    ).strip()
                    final_content = f"{rendered_tmpl}\n\n# {title_heading}\n\n{clean_content}\n"
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

            with open(target_file, "w", encoding="utf-8") as f:
                f.write(final_content)
            cls._reindex_note_if_enabled(mv, target_file)
            cls._update_manifest_if_enabled(mv, target_file)
            return f"Saved to note: `{rel_display}`"
        except Exception as e:
            return f"Error: Failed to write note: {e}"

    @classmethod
    def append_note(cls, profile: Dict[str, Any], note_name: str, content: str) -> str:
        mv, allowed_dirs, primary_dir = cls._get_master_vault(), cls.get_allowed_dirs(profile), cls.get_primary_dir(profile)
        if not mv or not primary_dir: return "Warning: Master notes directory not configured or path denied."
        if not (note_name.endswith(".md") or note_name.endswith(".canvas")):
            note_name += ".md"
        target_file = os.path.join(mv, note_name) if ("/" in note_name or "\\" in note_name) else os.path.join(primary_dir, note_name)
        if not any(is_safe_path(target_file, allowed) for allowed in allowed_dirs):
            return f"Security Error: Target path `{note_name}` is outside assigned sandbox."

        rel_display = os.path.relpath(target_file, mv)
        try:
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            if not os.path.exists(target_file):
                return cls.write_note(profile, note_name, content)

            with open(target_file, "a", encoding="utf-8") as f:
                f.write(f"\n{content.strip()}\n")
            cls._reindex_note_if_enabled(mv, target_file)
            cls._update_manifest_if_enabled(mv, target_file)
            return f"Appended to note: `{rel_display}`"
        except Exception as e:
            return f"Error: Failed to append note: {e}"

    # Sentinels the dashboard's `PUT` / `POST /api/vault/note` map onto HTTP status codes.
    NOTE_NOT_FOUND = "__note_not_found__"
    NOTE_DENIED = "__note_denied__"
    NOTE_EXISTS = "__note_exists__"

    @classmethod
    def overwrite_note(cls, profile: Dict[str, Any], note_name: str, content: str) -> str:
        """Replace an *existing* vault note's file with `content`, verbatim (the
        editor already owns the whole document, frontmatter included). Resolves
        the same file `read_note` would return, so a dashboard save lands back on
        the note it was opened from. Overwrite only — a path with no existing
        file returns `NOTE_NOT_FOUND` rather than creating one (ADR-081); a path
        outside the persona's sandbox returns `NOTE_DENIED`. On success the note
        is re-indexed and the manifest refreshed, exactly as `write_note` does.
        """
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return cls.NOTE_DENIED

        target_file = cls._resolve_existing_note(profile, note_name)
        if target_file is None:
            return cls.NOTE_NOT_FOUND
        if not any(is_safe_path(target_file, allowed) for allowed in allowed_dirs):
            return cls.NOTE_DENIED

        rel_display = os.path.relpath(target_file, mv)
        try:
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(content.rstrip("\n") + "\n")
            cls._reindex_note_if_enabled(mv, target_file)
            cls._update_manifest_if_enabled(mv, target_file)
            return f"Saved note: `{rel_display}`"
        except Exception as e:
            return f"Error: Failed to write note: {e}"

    @classmethod
    def create_note(cls, profile: Dict[str, Any], note_name: str, content: Optional[str] = None) -> str:
        """Create a *new* vault note from the dashboard (ADR-083). `note_name` is
        a path relative to the vault — `Folder/Sub/Title` — and is placed under
        the master vault when it contains a separator, otherwise in the persona's
        primary folder. Refuses (`NOTE_EXISTS`) rather than overwriting an
        existing file — that is `overwrite_note`'s job. `NOTE_DENIED` for a path
        outside the sandbox. When `content` is omitted a minimal
        frontmatter + title stub is seeded so the editor opens onto something
        editable. Re-indexed and added to the manifest like any other write."""
        mv, allowed_dirs, primary_dir = cls._get_master_vault(), cls.get_allowed_dirs(profile), cls.get_primary_dir(profile)
        if not mv or not allowed_dirs:
            return cls.NOTE_DENIED
        clean_name = note_name.strip().strip("\"'").lstrip("/\\")
        if not clean_name:
            return cls.NOTE_DENIED
        if not clean_name.endswith(".md"):
            clean_name += ".md"

        base = mv if ("/" in clean_name or "\\" in clean_name) else (primary_dir or mv)
        # `is_safe_path` resolves symlinks itself; keep `target_file` a plain
        # join so `os.path.relpath(…, mv)` here and in the re-index helpers
        # stays correct even when `mv` sits under a symlink (macOS `/var`).
        target_file = os.path.normpath(os.path.join(base, clean_name))
        if not any(is_safe_path(target_file, allowed) for allowed in allowed_dirs):
            return cls.NOTE_DENIED
        if os.path.exists(target_file):
            return cls.NOTE_EXISTS

        if content is None or not content.strip():
            title = os.path.splitext(os.path.basename(clean_name))[0].replace("_", " ").replace("-", " ").strip().title()
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            content = f"---\ntitle: {title}\ncreated: {today}\ntags: []\n---\n\n# {title}\n\n"

        rel_display = os.path.relpath(target_file, mv)
        try:
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(content if content.endswith("\n") else content + "\n")
            cls._reindex_note_if_enabled(mv, target_file)
            cls._update_manifest_if_enabled(mv, target_file)
            return f"Created note: `{rel_display}`"
        except Exception as e:
            return f"Error: Failed to create note: {e}"

    @classmethod
    def create_folder(cls, profile: Dict[str, Any], folder_name: str) -> str:
        """Create a new *empty* folder under the vault (ADR-095), alongside
        `create_note`'s path resolution and sandbox rules: `folder_name` is
        relative to the vault and lands under the master vault when it
        contains a separator, otherwise in the persona's primary folder.
        `NOTE_EXISTS` when the path is already a file or directory,
        `NOTE_DENIED` outside the sandbox."""
        mv, allowed_dirs, primary_dir = cls._get_master_vault(), cls.get_allowed_dirs(profile), cls.get_primary_dir(profile)
        if not mv or not allowed_dirs:
            return cls.NOTE_DENIED
        clean_name = folder_name.strip().strip("\"'").strip("/\\")
        if not clean_name:
            return cls.NOTE_DENIED

        base = mv if ("/" in clean_name or "\\" in clean_name) else (primary_dir or mv)
        target_dir = os.path.normpath(os.path.join(base, clean_name))
        if not any(is_safe_path(target_dir, allowed) for allowed in allowed_dirs):
            return cls.NOTE_DENIED
        if os.path.exists(target_dir):
            return cls.NOTE_EXISTS

        rel_display = os.path.relpath(target_dir, mv)
        try:
            os.makedirs(target_dir)
            return f"Created folder: `{rel_display}`"
        except Exception as e:
            return f"Error: Failed to create folder: {e}"

    @classmethod
    def delete_folder(cls, profile: Dict[str, Any], folder_name: str) -> str:
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
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return cls.NOTE_DENIED
        clean_name = folder_name.strip().strip("\"'").strip("/\\")
        if not clean_name:
            return cls.NOTE_DENIED
        target_dir = os.path.normpath(os.path.join(mv, clean_name))
        if not any(is_safe_path(target_dir, allowed) for allowed in allowed_dirs):
            return cls.NOTE_DENIED
        if not os.path.isdir(target_dir):
            return cls.NOTE_NOT_FOUND

        rel_display = os.path.relpath(target_dir, mv)
        if not os.listdir(target_dir):
            try:
                os.rmdir(target_dir)
                return f"Deleted empty folder: `{rel_display}`"
            except OSError as e:
                return f"Error: Failed to delete folder: {e}"

        dest = os.path.join(mv, vault_trash.TRASH_DIRNAME, clean_name)
        if not is_safe_path(dest, mv):
            return cls.NOTE_DENIED
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if os.path.exists(dest):
                dest = f"{dest}-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            os.rename(target_dir, dest)
        except OSError as e:
            return f"Error: Failed to delete folder: {e}"

        ws = cls._workspace_dir()
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
                    log.debug("[vault] folder-delete de-index failed for %s", orig_rel, exc_info=True)
                note_count += 1
        _BACKLINK_CACHE.clear()
        plural = "s" if note_count != 1 else ""
        dest_rel = os.path.relpath(dest, mv).replace(os.sep, "/")
        return f"Moved folder to the bin: `{dest_rel}` ({note_count} note{plural})"

    @classmethod
    def _resolve_existing_note(cls, profile: Dict[str, Any], note_name: str) -> Optional[str]:
        """Absolute path of the file `read_note` would open for `note_name`, or
        `None`: direct path under the master vault → basename in an allowed
        folder → recursive case-insensitive stem match. Shared by
        `overwrite_note` / `rename_note` / `delete_note`."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return None
        clean = note_name.strip().strip("\"'")
        if not clean.endswith(".md"):
            clean += ".md"

        direct = os.path.join(mv, clean)
        for allowed in allowed_dirs:
            if is_safe_path(direct, allowed) and os.path.isfile(direct):
                return direct
        for allowed in allowed_dirs:
            cand = os.path.join(allowed, os.path.basename(clean))
            if is_safe_path(cand, allowed) and os.path.isfile(cand):
                return cand
        stem = os.path.splitext(os.path.basename(clean))[0].lower()
        raw_ignore = config_manager.get("vault.ignore_folders") or [".obsidian", ".git", "Attachments", ".trash"]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        for allowed in allowed_dirs:
            for root, dirs, files in os.walk(allowed):
                dirs[:] = [d for d in dirs if d.lower() not in ignore_dirs and not d.startswith(".")]
                for fn in files:
                    if fn.endswith(".md") and os.path.splitext(fn)[0].lower() == stem:
                        fp = os.path.join(root, fn)
                        if is_safe_path(fp, allowed):
                            return fp
        return None

    _WIKILINK_RE = re.compile(r"(!?)\[\[([^\[\]\r\n]+?)\]\]")

    @classmethod
    def _rewrite_wikilink_targets(cls, text: str, old_stem: str, new_stem: str) -> Tuple[str, int]:
        """Retarget every `[[old]]` / `![[old]]` / `[[old#h]]` / `[[old|a]]`
        (and the `Folder/old` path form) to `new_stem`, leaving any `#heading`
        and `|alias` intact. Returns the rewritten text and the hit count."""
        old_l = old_stem.strip().lower()

        def repl(m: "re.Match[str]") -> str:
            bang, inner = m.group(1), m.group(2)
            head = re.match(r"^([^#|]*)(.*)$", inner)
            target, tail = head.group(1), head.group(2)
            segs = target.split("/")
            if segs[-1].strip().lower() != old_l:
                return m.group(0)
            segs[-1] = new_stem
            return f"{bang}[[{'/'.join(segs)}{tail}]]"

        new_text, n = cls._WIKILINK_RE.subn(repl, text)
        return new_text, n

    @classmethod
    def rename_note(cls, profile: Dict[str, Any], old_name: str, new_name: str) -> str:
        """Rename a vault note and rewrite every `[[wikilink]]` that pointed at
        it (ADR-084). `new_name` stays in the same folder unless it carries a
        separator. `NOTE_NOT_FOUND` / `NOTE_EXISTS` / `NOTE_DENIED` as for the
        other note ops."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return cls.NOTE_DENIED
        src = cls._resolve_existing_note(profile, old_name)
        if src is None:
            return cls.NOTE_NOT_FOUND

        clean_new = new_name.strip().strip("\"'").lstrip("/\\")
        if not clean_new:
            return cls.NOTE_DENIED
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
            return cls.NOTE_DENIED
        if os.path.exists(dst):
            return cls.NOTE_EXISTS

        old_rel, new_rel = os.path.relpath(src, mv), os.path.relpath(dst, mv)
        old_stem = os.path.splitext(os.path.basename(src))[0]
        new_stem = os.path.splitext(os.path.basename(dst))[0]
        ref_files = sorted({b["rel_path"] for b in cls.get_backlinks(profile, old_stem)})

        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.rename(src, dst)
        except OSError as e:
            return f"Error: Failed to rename note: {e}"

        updated = 0
        for rel in ref_files:
            fp = os.path.join(mv, rel)
            if rel == old_rel or not os.path.isfile(fp):
                continue
            if not any(is_safe_path(fp, allowed) for allowed in allowed_dirs):
                continue
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                rewritten, hits = cls._rewrite_wikilink_targets(content, old_stem, new_stem)
                if hits:
                    with open(fp, "w", encoding="utf-8") as f:
                        f.write(rewritten)
                    updated += 1
                    cls._reindex_note_if_enabled(mv, fp)
                    cls._update_manifest_if_enabled(mv, fp)
            except OSError:
                continue

        ws = cls._workspace_dir()
        ignore = config_manager.get("vault.ignore_folders") or []
        try:
            vault_index.remove_note(ws, mv, old_rel)
            vault_manifest.remove_note(ws, mv, old_rel, ignore_folders=ignore)
        except Exception:
            log.debug("[vault] rename de-index failed for %s", old_rel, exc_info=True)
        cls._reindex_note_if_enabled(mv, dst)
        cls._update_manifest_if_enabled(mv, dst)
        _BACKLINK_CACHE.clear()

        tail = f" ({updated} file{'s' if updated != 1 else ''} relinked)" if updated else ""
        return f"Renamed to `{new_rel}`{tail}"

    @classmethod
    def delete_note(cls, profile: Dict[str, Any], note_name: str) -> str:
        """Move a vault note to `<vault>/.trash/` preserving its relative path
        (ADR-084) — recoverable, and `.trash` is already an ignored folder. A
        name clash in the trash gets a timestamp suffix."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return cls.NOTE_DENIED
        src = cls._resolve_existing_note(profile, note_name)
        if src is None:
            return cls.NOTE_NOT_FOUND
        if not any(is_safe_path(src, allowed) for allowed in allowed_dirs):
            return cls.NOTE_DENIED

        old_rel = os.path.relpath(src, mv)
        dest = os.path.join(mv, vault_trash.TRASH_DIRNAME, old_rel)
        # `get_allowed_dirs` only ever returns folders under `mv`, so `old_rel`
        # can't carry a `..` prefix — but assert the trash target stays in-bounds
        # rather than trust that invariant from a distance.
        if not is_safe_path(dest, mv):
            return cls.NOTE_DENIED
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if os.path.exists(dest):
                stem, ext = os.path.splitext(dest)
                dest = f"{stem}-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
            os.rename(src, dest)
            # `os.rename` keeps the note's own mtime; stamp it to now so the
            # trash view's "deleted N ago" (ADR-085) reflects the deletion, not
            # the last edit.
            os.utime(dest, None)
        except OSError as e:
            return f"Error: Failed to delete note: {e}"

        ws = cls._workspace_dir()
        try:
            vault_index.remove_note(ws, mv, old_rel)
            vault_manifest.remove_note(ws, mv, old_rel, ignore_folders=config_manager.get("vault.ignore_folders") or [])
        except Exception:
            log.debug("[vault] delete de-index failed for %s", old_rel, exc_info=True)
        _BACKLINK_CACHE.clear()
        return f"Moved to the bin: `{os.path.relpath(dest, mv)}`"

    # ------------------------------------------------------------------
    # Trash recovery (ADR-085) — thin, sandbox-scoped wrappers over
    # `vault_trash`. Restore re-indexes the note so it is searchable and
    # back on the graph immediately; purge needs nothing (the file left
    # the index when it was trashed).
    # ------------------------------------------------------------------

    _TRASH_SENTINEL_MAP = {
        vault_trash.NOT_IN_TRASH: NOTE_NOT_FOUND,
        vault_trash.TARGET_EXISTS: NOTE_EXISTS,
        vault_trash.DENIED: NOTE_DENIED,
    }

    @classmethod
    def list_trash(cls, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Recoverable notes in `<vault>/.trash`, scoped to the persona's allowed
        folders, newest deletion first (ADR-085)."""
        mv, allowed = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed:
            return []
        return vault_trash.list_trashed(mv, allowed)

    @classmethod
    def restore_from_trash(cls, profile: Dict[str, Any], trash_path: str) -> str:
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
        _BACKLINK_CACHE.clear()
        return f"Restored to `{result}`"

    @classmethod
    def purge_from_trash(cls, profile: Dict[str, Any], trash_path: str) -> str:
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
    def empty_trash(cls, profile: Dict[str, Any]) -> str:
        """Permanently delete every in-scope trashed note (ADR-085)."""
        mv, allowed = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed:
            return cls.NOTE_DENIED
        n = vault_trash.purge_all(mv, allowed)
        return f"Emptied the bin ({n} note{'s' if n != 1 else ''})"

    @classmethod
    def _sync_frontmatter_tags(cls, file_path: str, new_tags: List[str]) -> None:
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
                existing_tags = [re.sub(r"^\s*-\s*", "", l).strip() for l in m_tags.group(1).splitlines() if l.strip()]
            elif m_inline:
                existing_tags = [t.strip().strip("\"'") for t in m_inline.group(1).split(",") if t.strip()]

            merged = list(dict.fromkeys(existing_tags + [t.lower() for t in new_tags if t]))
            tags_yaml = "tags:\n" + "\n".join([f"  - {t}" for t in merged])

            if m_tags:
                new_fm = fm_body[:m_tags.start()] + tags_yaml + fm_body[m_tags.end():]
            elif m_inline:
                new_fm = re.sub(r"tags:\s*\[.*?\]", tags_yaml, fm_body)
            elif "tags:" in fm_body:
                new_fm = re.sub(r"tags:.*", tags_yaml, fm_body)
            else:
                new_fm = fm_body.strip() + "\n" + tags_yaml

            updated_doc = f"---\n{new_fm.strip()}\n---\n" + doc[m.end():]
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(updated_doc)
        except Exception:
            pass

    @classmethod
    def write_daily_note(cls, profile: Dict[str, Any], reflection: str) -> str:
        now = datetime.datetime.now()
        daily_fmt = os.getenv("DAILY_NOTES_FORMAT", "Daily/%Y/%m-%B/%Y-%m-%d.md")
        clean_ref = reflection.strip()

        # Extract tags from reflection
        found_tags = list(dict.fromkeys(re.findall(r"#([a-zA-Z0-9_\-]+)", clean_ref)))
        if not found_tags:
            found_tags = ["jour", "reflection"]
        elif "jour" not in [t.lower() for t in found_tags]:
            found_tags.insert(0, "jour")

        # Guarantee that daily entries always possess Obsidian tags footer
        if not re.search(r"(?:tags:|\b#jour\b)", clean_ref, re.I):
            clean_ref = f"{clean_ref}\n\nTags: " + " ".join(f"#{t}" for t in found_tags)

        note_rel_path = now.strftime(daily_fmt)
        res = cls.append_note(profile, note_rel_path, f"\n### Reflection ({now.strftime('%H:%M')})\n{clean_ref}")

        # Sync frontmatter tags at top of the file
        mv = cls._get_master_vault()
        if mv:
            target_file = os.path.join(mv, note_rel_path)
            cls._sync_frontmatter_tags(target_file, found_tags)

        return res

    @classmethod
    def write_session_note(cls, profile: Dict[str, Any], summary_md: str, subfolder: str = "Sessions", session_title: Optional[str] = None) -> str:
        primary_dir, mv = cls.get_primary_dir(profile), cls._get_master_vault()
        if not primary_dir or not mv: return "Warning: Master notes directory not configured or path denied."
        now, handle = datetime.datetime.now(), profile.get("handle", "agent").lower()
        title_slug = f"_{session_title.lower().replace(' ', '_')}" if session_title else ""
        target_dir = os.path.join(primary_dir, subfolder)
        target_file = os.path.join(target_dir, f"{now.strftime('%Y-%m-%d_%H%M')}_{handle}{title_slug}_session.md")
        try:
            os.makedirs(target_dir, exist_ok=True)
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(f"---\nentry: {now.strftime('%Y-%m-%d')}\ncreated: {now.strftime('%Y-%m-%d %H:%M')}\ntype: session-log\nproject: sympose\nauthor: {profile.get('name', handle)}\ntags:\n  - session/log\n  - sympose/{handle}\n---\n\n# Session Log: {profile.get('name', handle)} ({now.strftime('%Y-%m-%d %H:%M')})\n\n{summary_md.strip()}\n")
            return f"Saved session note to Obsidian: `{os.path.relpath(target_file, mv)}`"
        except Exception as e:
            return f"Error: Failed to write session note: {e}"

    @classmethod
    def has_vault_skill(cls, profile: Dict[str, Any]) -> bool:
        """Verifies if the persona possesses the vault_recall skill."""
        skills = profile.get("skills") or []
        return "vault_recall" in skills

    @staticmethod
    def _allowed_rel_prefixes(mv: str, allowed_dirs: List[str]) -> List[str]:
        """`allowed_dirs` as vault-relative "Foo/"-style prefixes; "" means the
        whole vault. For filtering the whole-vault manifest down to a persona's
        sandbox without touching disk."""
        out: List[str] = []
        mv_real = os.path.realpath(mv)
        for a in allowed_dirs:
            if os.path.realpath(a) == mv_real:
                return [""]
            out.append(os.path.relpath(a, mv).replace(os.sep, "/").rstrip("/") + "/")
        return out

    @classmethod
    def find_chronological_notes(cls, profile: Dict[str, Any]) -> List[str]:
        """Dynamically discovers all chronological, daily, and journal notes across allowed vault folders."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return []

        # Manifest fast-path (ADR-078) — no filesystem walk when the map is live.
        manifest = cls.get_manifest()
        if manifest is not None:
            date_re = re.compile(r"^\d{4}-\d{2}-\d{2}\.(?:md|markdown|txt)$", re.I)
            prefixes = cls._allowed_rel_prefixes(mv, allowed_dirs)
            hits: List[str] = []
            for n in manifest.get("nodes", []):
                rel = str(n.get("rel_path", "")).replace(os.sep, "/")
                if not n.get("exists") or not rel.endswith((".md", ".markdown", ".txt")) or rel.endswith(".excalidraw.md"):
                    continue
                if not any(p == "" or rel.startswith(p) for p in prefixes):
                    continue
                folder_low = os.path.dirname(rel).lower()
                if date_re.match(os.path.basename(rel)) or "daily" in folder_low or "journal" in folder_low or "diary" in folder_low:
                    hits.append(os.path.join(mv, n["rel_path"]))
            return hits

        raw_ignore = config_manager.get("vault.ignore_folders") or [".obsidian", ".git", "Attachments", ".trash", "Drawings"]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}\.(?:md|markdown|txt)$")

        results: List[str] = []
        for allowed in allowed_dirs:
            if not os.path.exists(allowed):
                continue
            for root, dirs, files in os.walk(allowed):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in ignore_dirs]
                for fn in files:
                    if fn.endswith((".md", ".markdown", ".txt")) and not fn.endswith(".excalidraw.md"):
                        fp = os.path.join(root, fn)
                        if is_safe_path(fp, allowed):
                            if date_pattern.match(fn) or "daily" in root.lower() or "journal" in root.lower() or "diary" in root.lower():
                                results.append(fp)
        return results

    @classmethod
    def get_discovered_folders(cls, profile: Dict[str, Any]) -> Dict[str, str]:
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
                prefix = (os.path.relpath(allowed, mv).replace(os.sep, "/").rstrip("/") + "/") if scoped else ""
                if scoped:
                    discovered[os.path.basename(allowed).lower()] = allowed
                for key in folder_keys:
                    k = key.replace(os.sep, "/")
                    if prefix and not k.startswith(prefix):
                        continue
                    rest = k[len(prefix):]
                    if rest and "/" not in rest:            # immediate child only
                        discovered[rest.lower()] = os.path.join(mv, key)
            return discovered

        raw_ignore = config_manager.get("vault.ignore_folders") or [".obsidian", ".git", "Attachments", ".trash", "Drawings"]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        discovered: Dict[str, str] = {}

        for allowed in allowed_dirs:
            if not os.path.exists(allowed):
                continue
            if allowed != mv:
                discovered[os.path.basename(allowed).lower()] = allowed
            try:
                for entry in os.scandir(allowed):
                    if entry.is_dir() and not entry.name.startswith(".") and entry.name.lower() not in ignore_dirs:
                        discovered[entry.name.lower()] = entry.path
            except Exception:
                pass
        return discovered

    @classmethod
    def _recall_hit(cls, profile: Dict[str, Any], cand: str, target_folder: Optional[str] = None) -> Optional[str]:
        """Search one candidate term for the conversational-recall fallback.
        A single result — or a clear title match on the first hit — returns the
        note's *full verbatim body* (the strongest possible grounding payload);
        anything broader returns the ranked digest so the model can pick."""
        results = cls.search_structured(profile, cand, target_folder=target_folder)
        if not results:
            return None
        top = results[0]
        if len(results) == 1 or top.get("match_type") == "title":
            body = cls.read_note(profile, top.get("rel_path") or top.get("file_name", ""))
            if body and not body.startswith(("⚠️", "Error reading", "Note `")):
                loc = f" in `{target_folder}/`" if target_folder else ""
                return (f"### Ground-Truth Sandboxed Vault Note (`{top.get('rel_path')}` "
                        f"— Exact Content, matched '{cand}'{loc}):\n{body[:3500]}")
        digest = cls.format_search_digest(cand, results)
        loc = f" in `{target_folder}/`" if target_folder else ""
        return f"### Ground-Truth Vault Search Results for '{cand}'{loc}:\n{digest}"

    @classmethod
    def resolve_turn_context(cls, profile: Dict[str, Any], message: str) -> Optional[str]:
        """Skill-gated, structure-agnostic pre-inference retrieval conforming to skills/vault_recall."""
        # 1. Skill Permission Gate: only proceed if agent is authorized for vault recall
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
        if (re.search(r"\b(vault|obsidian|journal|(?:my|our|the)\s+notes?)\b", msg, re.I)
                and re.search(r"\b(structure|structured|organi[sz]\w+|hierarch\w+|layout|"
                              r"topolog\w+|folders?|sub-?folders?|breakdown|stats?|status|"
                              r"summary|overview|snapshot|inventory|shape|size|"
                              r"how many|how much|how big|how large|how'?s|hows|"
                              r"what'?s in|state of|count)\b", msg, re.I)
                and not re.search(r"\babout\b|\bregarding\b|[\"'][^\"']{2,}[\"']", msg)):
            manifest = cls.get_manifest()
            if manifest and manifest.get("nodes"):
                return cls.format_manifest_digest(manifest)

        # 2. Wikilink & Backlink Queries ("what notes link to [[OAuth]]?", "backlinks for Architecture")
        bl_match = re.search(
            r"(?:what\s+(?:notes\s+)?(?:link\s+to|reference)|who\s+(?:links\s+to|references)|backlinks?\s+(?:for|to|of)?)\s+(?:\[\[)?([a-zA-Z0-9_\-\s/\.]+?)(?:\]\])?(?:\?|$|\.|\n)",
            msg,
            re.I
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
                if content and not content.startswith("Note `") and not content.startswith("⚠️"):
                    return f"### Ground-Truth Sandboxed Vault Note (`{q_clean}` - Exact Content):\n{content}"

        # 4. Explicit note reading requests ("read note X", "look at note X")
        rd = re.search(r"(?:read|open|check|look\s+at|show\s+me)\s+(?:the\s+)?note\s+([a-zA-Z0-9_\-/\.\s]+(?:\.md|\.markdown|\.txt|[a-zA-Z0-9]))", msg, re.I)
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

        # 5. Chronological & Daily Journal Intent (Structure-Agnostic)
        is_chrono_query = bool(re.search(r"\b(daily|journal|diary|reflection|reflections|log|logs|day's\s+note|entry|entries)\b", msg, re.I))
        # Only an *explicit* ask for an arbitrary note — "pull"/"grab"/"get"/
        # "pick" alone are not it ("pull up Dylan's entry" names a target).
        is_sample_request = bool(re.search(
            r"\b(?:random(?:ly)?|randam|rnd|surprise\s+me|a\s+random|any\s+(?:random\s+)?(?:one|note|entry|day)|"
            r"some\s+(?:random\s+)?(?:note|entry|day)|(?:pick|choose|grab|pull\s+up|show|give)\s+(?:me\s+)?(?:a|an|one|any)\b|"
            r"one\s+of\s+(?:my|the|our)|whatever\s+comes\s+up)\b",
            msg, re.I,
        ))

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
                except Exception:
                    pass

        # 6. Year-based chronological queries ("2020 journal entry")
        yr = re.search(r"\b(201\d|202\d|19\d\d)\b", msg)
        if yr and is_chrono_query:
            res = cls.search(profile, yr.group(1))
            if res and not res.startswith("No notes found") and "not configured" not in res:
                return f"### Ground-Truth Vault Search Results for '{yr.group(1)}':\n{res}"

        # 7. Dynamic Real-Directory Discovery & Sampling (Zero Hardcoding)
        discovered_dirs = cls.get_discovered_folders(profile)
        triggers = config_manager.get("vault.search_triggers") or [
            "vault", "note", "notes", "folder", "journal", "backlink", "backlinks",
            "search", "find", "lookup", "look up", "recall", "remind me", "pull up",
            "what did i write", "what did i say", "do i have", "do we have",
        ]
        has_intent = any(k in msg.lower() for k in triggers)

        if has_intent and discovered_dirs:
            for folder_name, folder_path in discovered_dirs.items():
                f_stem = folder_name.rstrip("s")
                if re.search(rf"\b{re.escape(f_stem)}\w*\b", msg, re.I):
                    if is_sample_request and not subject:
                        samples = cls.get_random_sample_notes(profile, folder_name, count=1)
                        if samples:
                            return f"### Ground-Truth Selected Note from `{folder_name}/`:\n{samples}"
                    if re.search(r"\b(scan|analyze|summarize|all|overview|connections?|access)\b", msg, re.I):
                        return cls.get_folder_digest(profile, folder_name)
                    # A named subject alongside the folder ("Dylan's People entry")
                    # means search *that* inside the folder, not list the folder.
                    # A named subject alongside the folder ("Dylan's People entry")
                    # means search *that* inside the folder, not list the folder.
                    if subject:
                        for st in cls._recall_candidates(subject, drop=f_stem):
                            hit = cls._recall_hit(profile, st, target_folder=folder_name)
                            if hit:
                                return hit
                    res = cls.search(profile, folder_name, target_folder=folder_name)
                    if res and not res.startswith("No notes found") and "not configured" not in res:
                        return f"### Ground-Truth Vault Search Results for '{folder_name}':\n{res}"

        # 8. Conversational recall fallback — search the extracted subject,
        #    retrying progressively narrower so a multi-word phrase that
        #    substring-matches nothing still surfaces its salient notes.
        if (has_intent or had_leadin) and subject and len(subject) >= 3:
            for cand in cls._recall_candidates(subject):
                hit = cls._recall_hit(profile, cand)
                if hit:
                    return hit

        return None

    @classmethod
    def _recall_candidates(cls, subject: str, drop: str = "") -> List[str]:
        """Ordered search terms for a recall subject: the full phrase first, then
        its most-specific single tokens (longest, then earliest), then the
        de-pluralised stem of each so an apostrophe-less possessive ('dylans' ->
        'dylan') still matches. `drop` removes one token (e.g. the folder name)."""
        toks = {t for t in subject.split() if len(t) >= 3 and t not in cls._SUBJECT_STOPWORDS and t != drop}
        toks |= {t[:-1] for t in list(toks) if len(t) >= 5 and t.endswith("s")}
        ordered = [subject] + sorted(toks, key=lambda t: (-len(t), subject.find(t)))
        seen: set = set()
        out: List[str] = []
        for c in ordered:
            c = c.strip()
            if len(c) >= 3 and c not in seen:
                seen.add(c)
                out.append(c)
        return out
