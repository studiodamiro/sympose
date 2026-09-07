"""
Declarative prompt templates shipped inside the package.

The Markdown templates live at ``sympose/prompts/*.md`` so they are covered by
``[tool.setuptools.package-data]`` and are present in every wheel / pipx
install. A bare top-level ``prompts/`` directory is *not* shipped in the wheel,
which previously forced every non-editable install onto the terse inline
fallback strings in ``bootstrap``, ``memory`` and ``workers``.
"""

import os

_PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")


def load_prompt(name: str, fallback: str = "") -> str:
    """Returns the stripped body of ``sympose/prompts/<name>``, or ``fallback``
    if the file is missing or unreadable (corrupt install)."""
    try:
        with open(os.path.join(_PROMPTS_DIR, name), "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return fallback
