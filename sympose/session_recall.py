"""
Conversational session-recall intent detection: recognizing when a message
asks about Sympose's OWN past conversations ("what did we do last session?",
"what did we talk about yesterday?", "pick up where we left off") rather than
a request to search the user's Obsidian vault. Pure text processing, no I/O —
same split as vault_recall.py, and deliberately kept as its own trigger list
rather than folded into vault_recall's: the two ask fundamentally different
questions ("what's in my notes" vs "what did we just talk about"), and a
shared word list would risk a genuine vault question ("what did I write in my
journal last time") answering from the wrong store.
"""

import re

_SESSION_RECALL_RE = re.compile(
    r"\b(?:what|how)\s+(?:did|have)\s+(?:we|you)\s+(?:do|talk(?:ed)?|discuss(?:ed)?|"
    r"work(?:ed)?\s+on|cover(?:ed)?|say)\b.{0,20}\b(?:last|previous|prior|"
    r"yesterday|earlier|before)\b"
    r"|\b(?:our|that)\s+last\s+(?:session|conversation|chat|talk)\b"
    r"|\blast\s+(?:time\s+we\s+(?:spoke|talked|chatted)|session|conversation)\b"
    r"|\bpick\s+up\s+where\s+we\s+left\s+off\b"
    r"|\bcatch\s+me\s+up\s+on\s+(?:our\s+)?(?:last|previous)\s+"
    r"(?:session|conversation|chat)\b"
    r"|\bwhat\s+(?:were\s+we|was\s+i)\s+(?:doing|working\s+on|discussing)\s+"
    r"(?:last|previously|before)\b",
    re.IGNORECASE,
)


def has_session_recall_intent(message: str) -> bool:
    """True when the message is asking about a past SYMPOSE CONVERSATION
    with this persona — never a signal to search the user's Obsidian vault.
    Deliberately conservative (specific phrasings, not a bare 'recent' or
    'last' keyword) so it doesn't fire on an unrelated question that happens
    to mention time."""
    return bool(_SESSION_RECALL_RE.search(message.strip().lower()))
