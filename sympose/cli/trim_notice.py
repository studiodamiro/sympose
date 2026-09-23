"""The reply header's context notices (docs/decisions/015): how many older
turns were left out of what the model was sent because they did not fit its
window, and whether the reply stopped at its length limit. Each shown only on
turns where it happened; both behind one setting."""

from sympose import settings_store

SETTING = "show_trim_notice"


def enabled() -> bool:
    return settings_store.flag(SETTING)


def segment(dropped: int, truncated: bool = False) -> str:
    """` \u00b7 3 older turns out of context` (and ` \u00b7 reply cut at the length
    limit`) to append to the header, or `""` when there is nothing to say or the
    notices are turned off."""
    if not enabled():
        return ""
    notice = ""
    if dropped > 0:
        notice += f" \u00b7 {dropped} older {'turn' if dropped == 1 else 'turns'} out of context"
    if truncated:
        notice += " \u00b7 reply cut at the length limit"
    return notice
