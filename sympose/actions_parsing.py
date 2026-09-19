"""
Tag-scanning and result-classification helpers for `ActionProcessor`
(ADR-137, split out of actions.py) — finding/extracting `[TAG: ...]`
occurrences in model output, independent of what any tag's handler
actually does. `TAG_NAMES`/`_PSEUDO_TAG_RE`/`MAX_ACTION_DEPTH` stay in
actions.py itself: `_PSEUDO_TAG_RE`'s own construction embeds `TAG_NAMES`
at class-body-execution time, so both must live in the same class body as
each other, not split across mixins.
"""

import re


class ParsingMixin:
    @staticmethod
    def _op_failed(result: str) -> bool:
        """True when a vault_write.py-style call returned one of its
        established failure prefixes instead of a success message. Every
        call site that shows a confirmation badge must check this first —
        write_note/append_note/write_daily_note return a string either way,
        and nothing upstream previously distinguished them, so a rejected
        write (sandbox violation, the Daily/ boundary guard, a disk error)
        was confirmed to the user as a success every time."""
        return isinstance(result, str) and result.startswith(
            ("Error", "Security Error", "Warning")
        )

    @staticmethod
    def _match_tag_prefix(text: str, i: int, tag: str) -> int:
        """Length of a `[TAG:` or `[ACTION:TAG:` prefix at position `i`
        (case-insensitive), or 0 if neither matches."""
        prefix = f"[{tag}:"
        prefix_act = f"[ACTION:{tag}:"
        upper = text[i:].upper()
        if upper.startswith(prefix):
            return len(prefix)
        if upper.startswith(prefix_act):
            return len(prefix_act)
        return 0

    @staticmethod
    def _find_matching_bracket(text: str, start: int) -> int | None:
        """Index just past the `]` that closes the `[` at `start`, counting
        nested brackets - or None if it's never closed before the text
        ends."""
        depth = 1
        j = start + 1
        while j < len(text) and depth > 0:
            if text[j] == "[":
                depth += 1
            elif text[j] == "]":
                depth -= 1
            j += 1
        return j if depth == 0 else None

    @classmethod
    def _consume_tag_at(
        cls, text: str, i: int, results: list[tuple[str, str, str]]
    ) -> int:
        """If a recognized tag starts at `i`, parses it (appending to
        `results` unless it's a documentation template placeholder) and
        returns the index of its closing `]`, so the outer scan can resume
        just past it; otherwise returns `i` unchanged (an unrecognized or
        never-closed bracket is left for the outer scan to step past one
        character at a time, same as plain literal text)."""
        for tag in cls.TAG_NAMES:
            p_len = cls._match_tag_prefix(text, i, tag)
            if not p_len:
                continue
            j = cls._find_matching_bracket(text, i)
            if j is None:
                break
            raw_tag = text[i:j]
            inner = text[i + p_len : j - 1].strip()
            # Ignore documentation template placeholders (e.g. <handle>, <manifest>, <path>, etc.)
            if not re.search(
                r"<(?:handle|manifest|path|content|reflection_content|query|folder|key|value|target|spec)[^>]*>",
                inner,
                re.IGNORECASE,
            ):
                results.append((tag, inner, raw_tag))
            return j - 1
        return i

    @classmethod
    def parse_action_tags(cls, text: str) -> list[tuple[str, str, str]]:
        """Extracts all autonomic action tags supporting nested brackets while ignoring documentation template placeholders."""
        results: list[tuple[str, str, str]] = []
        i = 0
        while i < len(text):
            if text[i] == "[":
                i = cls._consume_tag_at(text, i, results)
            i += 1
        return results

    @classmethod
    def strip_action_tags(cls, text: str) -> str:
        """Strips raw action tags from text without executing them."""
        tags = cls.parse_action_tags(text)
        clean = text
        for _, _, raw_tag in tags:
            clean = clean.replace(raw_tag, "")
        clean = cls._PSEUDO_TAG_RE.sub("", clean)
        clean = re.sub(r"```[a-zA-Z0-9_-]*\s*```\n?", "", clean)
        return re.sub(r"\n{3,}", "\n\n", clean).strip()

    # --- Tag-shape gates: does a tag's body look well-formed enough to run
    # its handler at all? False falls through to the generic malformed-tag
    # badge in execute_actions, matching each tag's own historical
    # condition (e.g. WRITE_NOTE needs a `|` separator; DAILY_NOTE just
    # needs a non-empty body; CREATE_PERSONA has no shape requirement).
    @staticmethod
    def _has_pipe(inner: str) -> bool:
        return "|" in inner

    @staticmethod
    def _non_empty(inner: str) -> bool:
        return bool(inner)

    @staticmethod
    def _non_empty_stripped(inner: str) -> bool:
        return bool(inner.strip())

    @staticmethod
    def _always_true(inner: str) -> bool:
        return True
