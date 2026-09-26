"""What reached the model besides the messages, as the session log keeps it (docs/decisions/025)."""

from typing import Any


def sent_record(
    grounding: list[dict[str, Any]],
    recaps: list[dict[str, Any]],
    searched: str | None,
    dropped: int,
    cloud: tuple[list[str], list[str]] | None = None,
) -> dict[str, Any]:
    """What reached the model besides the messages, for the session record
    (docs/decisions/025): where each note came from, never its text. `cloud`, for a model that is
    not local, is the categories sent and the categories held back (docs/decisions/031)."""
    return {
        "notes": [
            {
                "path": hit["rel_path"],
                "heading": hit.get("heading", ""),
                "source": hit.get("source", "vault"),
                **({"via": hit["via"]} if "via" in hit else {}),  # how it was found, when the knob is on (ADR 027)
            }
            for hit in grounding
        ],
        "recaps": [r["session"] for r in recaps],
        "searched": searched,
        "history_dropped": dropped,
        **({"cloud": cloud[0], "withheld": cloud[1]} if cloud else {}),
    }
