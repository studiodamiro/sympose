"""Shared sentinel result strings for vault write operations, so the server's
translation into HTTP status codes stays independent of which module a
result actually came from."""

NOTE_NOT_FOUND = "__note_not_found__"
NOTE_DENIED = "__note_denied__"
NOTE_EXISTS = "__note_exists__"
NOTE_INVALID_NAME = "__note_invalid_name__"
