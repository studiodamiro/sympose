"""
Sandboxed Vault & Markdown Note Manager for Sympose.
"""

import os, re, datetime, logging
import yaml
from typing import Dict, Any, Optional, List, Tuple
from collections import defaultdict
from sympose.config import is_safe_path, config_manager
from sympose import vault_index

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

        match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", content, re.DOTALL)
        if not match:
            return {}, content

        raw_yaml, body = match.group(1), match.group(2)
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
            return f"Appended to note: `{rel_display}`"
        except Exception as e:
            return f"Error: Failed to append note: {e}"

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

    @classmethod
    def find_chronological_notes(cls, profile: Dict[str, Any]) -> List[str]:
        """Dynamically discovers all chronological, daily, and journal notes across allowed vault folders."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return []

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
    def resolve_turn_context(cls, profile: Dict[str, Any], message: str) -> Optional[str]:
        """Skill-gated, structure-agnostic pre-inference retrieval conforming to skills/vault_recall."""
        # 1. Skill Permission Gate: only proceed if agent is authorized for vault recall
        if not cls.has_vault_skill(profile):
            return None

        msg = message.strip()
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return None

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

        # 5. Chronological & Daily Journal Intent (Structure-Agnostic)
        is_chrono_query = bool(re.search(r"\b(daily|journal|diary|reflection|reflections|log|logs|day's\s+note|entry|entries)\b", msg, re.I))
        is_sample_request = bool(re.search(r"\b(pick|choose|random|randam|rnd|surprise|sample|one\s+of|pull|grab|fetch|get\s+one|show\s+one|any)\b", msg, re.I))

        if is_chrono_query and is_sample_request:
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
                    if is_sample_request:
                        samples = cls.get_random_sample_notes(profile, folder_name, count=1)
                        if samples:
                            return f"### Ground-Truth Selected Note from `{folder_name}/`:\n{samples}"
                    if re.search(r"\b(scan|analyze|summarize|all|overview|connections?|access)\b", msg, re.I):
                        return cls.get_folder_digest(profile, folder_name)
                    res = cls.search(profile, folder_name, target_folder=folder_name)
                    if res and not res.startswith("No notes found") and "not configured" not in res:
                        return f"### Ground-Truth Vault Search Results for '{folder_name}':\n{res}"

        # 8. Conversational search fallback
        q = re.sub(r"^(?:hey|hi|hello|yo|good\s+\w+)\s*(?:\w+)?[\.\,\:\;–—\s\-]*", "", msg, flags=re.I).strip()
        q = re.sub(r"^(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?(?:how\s+about|what\s+about|do\s+we\s+have|is\s+there|tell\s+me\s+about|show\s+me|find|search|retrieve|check|look\s+(?:for|at)?|pick|get|pull)\s*", "", q, flags=re.I).strip()
        q = re.sub(r"^(?:(?:an?|the|some|any|random|randam|my|our)\s+)?(?:obsidian\s+)?(?:vault\s+)?(?:daily\s+|historical\s+)?(?:notes?|journals?|entries|entry|reflections?|posts?|logs?)\s*(?:wayback|from|in|about|for|regarding|on|discussing|mentioning|talking\s+about)?\s*", "", q, flags=re.I).strip()
        target_q = re.split(r"[,.!?]", q)[0].strip()
        if target_q and len(target_q) >= 3 and has_intent:
            res = cls.search(profile, target_q)
            if res and not res.startswith("No notes found") and "not configured" not in res:
                return f"### Ground-Truth Vault Search Results for '{target_q}':\n{res}"

        return None
