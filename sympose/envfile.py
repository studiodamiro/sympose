"""The `.env` file: only the one in the folder Sympose runs from, never one found by searching upward.

`load_dotenv()` with no path searches upward from the calling file, which for an installed copy (pipx) is inside
the virtual environment, so the user's own `.env` was never read; searching upward from the working folder instead
would also pick up a stray `.env` in a parent folder or the home folder. A variable already set in the
environment keeps its value."""

from pathlib import Path

from dotenv import load_dotenv


def load_env() -> None:
    load_dotenv(Path.cwd() / ".env")
