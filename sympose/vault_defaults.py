"""Vault-scan defaults. The legacy backend reads these from a persisted,
user-editable `ConfigManager` settings registry; this minimal port hardcodes
the same shipped default so vault walks skip the same noise without pulling
in that whole settings layer."""

IGNORE_FOLDERS: list[str] = [".obsidian", ".git", "Attachments", "Drawings", ".trash"]

# The file types the vault treats as notes (snapshot, note-name scan, file-change detection, link targets).
NOTE_EXTENSIONS = (".md", ".markdown", ".txt")

# File types Obsidian opens as attachments: a link or embed of one is not a link to a note.
ATTACHMENT_EXTENSIONS = frozenset(
    ".png .jpg .jpeg .gif .svg .webp .bmp .avif .mp3 .wav .ogg .m4a .flac .3gp .mp4 .webm .ogv .mov .mkv .pdf".split()
)
