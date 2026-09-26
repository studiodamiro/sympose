"""Request body models for the web API — split out of
`server_handlers.py` (project's 200-LOC-per-file guideline)."""

from pydantic import BaseModel, Field


class NoteWrite(BaseModel):
    """Body of `PUT /api/vault/note` — the web app editor saving an
    *existing* note back to the vault verbatim, frontmatter included."""

    path: str = Field(..., min_length=1)
    content: str
    persona: str | None = None
    expected_mtime: float | None = Field(
        None,
        description="mtime this save was opened from (from GET /api/vault/note). "
        "When given, a save is rejected with 409 if the file changed on disk "
        "since then, instead of silently overwriting it.",
    )


class NoteCreate(BaseModel):
    """Body of `POST /api/vault/note` — create a *new* note at `path`
    (relative to the vault, e.g. `Projects/Idea`). `content` is optional;
    omitted, the backend seeds a frontmatter + title stub."""

    path: str = Field(..., min_length=1)
    content: str | None = None
    persona: str | None = None


class FolderCreate(BaseModel):
    """Body of `POST /api/vault/folder` — create a new *empty* folder at
    `path` (relative to the vault, e.g. `Projects/Archive`)."""

    path: str = Field(..., min_length=1)
    persona: str | None = None


class NoteRename(BaseModel):
    """Body of `PATCH /api/vault/note` — rename `path` to `new_path` and
    rewrite every `[[wikilink]]` that referenced it. `new_path` stays in
    the same folder unless it carries a separator (then it is relative to
    the vault); a leading slash (`/name`) means the vault root."""

    path: str = Field(..., min_length=1)
    new_path: str = Field(..., min_length=1)
    persona: str | None = None


class TrashRestore(BaseModel):
    """Body of `POST /api/vault/trash/restore` — move the trashed note at
    `path` (a `.trash`-relative path from `GET /api/vault/trash`) back to
    where it was deleted from."""

    path: str = Field(..., min_length=1)
    persona: str | None = None


class TrashEmpty(BaseModel):
    """Body of `POST /api/vault/trash/empty` — permanently delete every
    in-scope trashed note."""

    persona: str | None = None


class VaultActivate(BaseModel):
    """Body of `POST /api/vaults/active` — switch the active vault to
    `path`, one of `GET /api/vaults`' configured paths."""

    path: str = Field(..., min_length=1)
