"""Shared test helpers — one directory per persona (docs/decisions/011)."""

from pathlib import Path


def write_persona(profiles_dir: Path, handle: str, body: str) -> Path:
    """Creates `<profiles_dir>/<handle>/persona.yaml` with `body` and
    returns the persona directory."""
    directory = profiles_dir / handle
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "persona.yaml").write_text(body)
    return directory
