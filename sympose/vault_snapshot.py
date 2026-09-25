"""
Vault content snapshot — a mtime-cached, flat read of every note under a set
of directories, shared by the tree/manifest projection so a web app
request doesn't re-walk and re-read the whole vault every time.
"""

import logging
import os
import re
from typing import Any

import yaml

from sympose import vault_paths
from sympose.security import is_safe_path
from sympose.vault_defaults import IGNORE_FOLDERS

log = logging.getLogger(__name__)

_VAULT_SNAPSHOT_CACHE: dict[tuple[str, ...], tuple[float, list[dict[str, Any]]]] = {}


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


def get_vault_snapshot(mv: str, dirs: list[str]) -> list[dict[str, Any]]:
    """Returns a cached, flat list of every note under `dirs` (path, parsed
    frontmatter, body, raw content), rebuilt only when a dir's mtime
    changes."""
    ignore_dirs = {d.lower() for d in IGNORE_FOLDERS}

    def build() -> list[dict[str, Any]]:
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
                            file_path, "r", encoding="utf-8", errors="replace"
                        ) as f:
                            full_content = f.read()
                    except Exception as e:
                        log.debug(
                            "Skipping unreadable file in snapshot %s: %s", file_path, e
                        )
                        continue
                    meta, body = parse_frontmatter(full_content)
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
        return snapshot

    return vault_paths.mtime_cached(_VAULT_SNAPSHOT_CACHE, dirs, ignore_dirs, build)
