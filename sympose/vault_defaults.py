"""Vault-scan defaults. The legacy backend reads these from a persisted,
user-editable `ConfigManager` settings registry; this minimal port hardcodes
the same shipped default so vault walks skip the same noise without pulling
in that whole settings layer."""

IGNORE_FOLDERS: list[str] = [".obsidian", ".git", "Attachments", "Drawings", ".trash"]
