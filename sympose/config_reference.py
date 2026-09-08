"""
Generator for `docs/wiki/reference/configuration.md` — the human-facing table of
every runtime knob, built straight from `config_schema.SETTINGS`.

Regenerate after adding or changing a `Setting`:

    python -m sympose.config_reference > docs/wiki/reference/configuration.md

`tests/unit/test_config_schema.py` fails if the committed file drifts from this
output, so the page cannot silently rot. Kept out of `config_schema.py` (and off
the package import path) so the schema module stays lean.
"""

from sympose.config_schema import SECTIONS, SETTINGS, Setting


def _allowed(s: Setting) -> str:
    if s.choices is not None:
        return " \\| ".join(f"`{c}`" for c in s.choices)
    if s.minimum is not None and s.maximum is not None:
        return f"{s.minimum}–{s.maximum}"
    if s.minimum is not None:
        return f"≥ {s.minimum}"
    if s.maximum is not None:
        return f"≤ {s.maximum}"
    return "—"


def _row(s: Setting) -> str:
    default = "*(unset)*" if s.default in (None, "") else f"`{s.default}`"
    live = "yes" if s.live else "**restart**"
    return f"| `{s.key}` | {s.type} | {default} | {_allowed(s)} | {live} | {s.description} |"


def render_reference_md() -> str:
    """Return the full Markdown for the configuration reference wiki page."""
    lines = [
        "---",
        'title: "Configuration Reference"',
        "created: 2026-09-08",
        "type: wiki-reference",
        "parent: index",
        "tags:",
        "  - sympose/reference",
        "  - config",
        "---",
        "",
        "# ⚙️ Configuration Reference",
        "",
        "> **Generated from `sympose/config_schema.py` — do not edit by hand.**",
        "> Regenerate with `python -m sympose.config_reference > "
        "docs/wiki/reference/configuration.md`.",
        "",
        "Every runtime knob Sympose reads. Global keys live in `config.yaml`, "
        "settable at runtime with `/config set <key> <value>`; persona keys live in "
        "`profiles/<handle>.yaml`, settable with `/persona set @<handle> <key> "
        "<value>`. **Live = yes** takes effect immediately; **restart** needs a "
        "fresh process.",
        "",
    ]
    for section in SECTIONS:
        rows = [s for s in SETTINGS if s.section == section]
        if not rows:
            continue
        lines += [
            f"## {section}",
            "",
            "| Key | Type | Default | Allowed | Live | Description |",
            "| --- | --- | --- | --- | --- | --- |",
            *[_row(s) for s in rows],
            "",
        ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(render_reference_md(), end="")
