"""Replacing a file whole or not at all. Split out of `vault_write` so the settings file, which
`vault_write` itself depends on, can be written the same way."""

import os
import shutil
import threading


def write_atomic_text(path: str, content: str, *, newline: str | None = None, errors: str = "strict") -> None:
    """Writes `content` to `path` via a tmp file + `os.replace` — the rename
    is atomic on the same filesystem, so a crash mid-write can't leave
    `path` truncated. The file keeps its permissions (a private note stays
    private) and a symlink is written through, not replaced. `newline=""`
    writes line endings exactly as they are in `content`, and
    `errors="surrogateescape"` writes back bytes that were read as such (a
    rewrite of an existing note must not change what it did not mean to)."""
    target = os.path.realpath(path)
    tmp = f"{target}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8", errors=errors, newline=newline) as f:
            f.write(content)
        if os.path.exists(target):
            shutil.copymode(target, tmp)
        os.replace(tmp, target)
    except BaseException:  # any failure, not only OSError: an unencodable character must not leave the tmp file
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
