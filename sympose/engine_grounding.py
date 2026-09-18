"""
Pure/static grounding-and-recall helpers for PersonaEngine — the checks
that decide whether a persona's reply is trustworthy (citation mismatch,
missing title, referent-less claim phrasing) and the small text-processing
utilities they lean on (entity guessing, ritual-continuation detection,
session-history digesting). Split out of engine.py per ADR-125 purely to
keep that file under this project's own size guidance; every method here
is unchanged from its prior home, so `PersonaEngine(GroundingHelpersMixin)`
is a pure move, not a rewrite.

Nearly everything here is a `@staticmethod`/`@classmethod` with no real
instance-state dependency; `_grounding_mode` is the one exception (it
reads `self.config`), which is exactly why this is a mixin rather than a
set of free functions — `self.config` keeps resolving normally once
`PersonaEngine` inherits from this class, with no parameter threading.
"""

import re
from typing import Any

from sympose.actions import ActionProcessor
from sympose.config import is_local_backend
from sympose.sessions import SessionManager
from sympose.vault import VAULT_PATH_TOKEN_RE, VaultManager


class GroundingHelpersMixin:
    # Start of an autonomic retrieval tag. Once the model emits one of these it
    # cannot yet know the result, so everything it streams afterwards is a guess
    # — the visible stream is cut here and the runtime injects the real report.
    _RETRIEVAL_TAG_RE = re.compile(
        r"\[(?:ACTION:)?(?:SEARCH|WEB_SEARCH|SPAWN_SUB_AGENT)\b", re.IGNORECASE
    )

    # Every autonomic action tag, not just retrieval ones - built from
    # ActionProcessor's own list so it can't quietly drift out of sync with
    # it. A tag's bracket syntax is internal wire format; without this, a
    # non-retrieval tag (WRITE_NOTE, REMEMBER, CONFIG_SET, ...) just sits in
    # _visible_stream's holdback buffer and gets unconditionally flushed
    # once the stream ends, leaking its raw `[WRITE_NOTE: ...]` text into
    # what the user actually sees, right next to the clean confirmation
    # badge for the same action.
    _ANY_ACTION_TAG_RE = re.compile(
        r"\[(?:ACTION:)?(?:" + "|".join(ActionProcessor.TAG_NAMES) + r")\b",
        re.IGNORECASE,
    )

    # Cloud chat APIs enforce the assistant/user turn boundary server-side.
    # Local backends only stop where the model's own template's stop token
    # fires — a mismatched or broken template (seen on some community
    # fine-tunes) lets generation run past the reply into a hallucinated
    # continuation. These are model-agnostic markers for that continuation,
    # applied as a `stop` list so it's cut regardless of the local model's
    # own template correctness.
    _LOCAL_RUNAWAY_STOP_SEQUENCES = (
        "\n### User:",
        "\n### Assistant:",
        "\nUser:",
        "\nYou (to",
    )

    # A reply that asserts it is reporting the user's own vault content. If one
    # of these fires and no retrieval ran this turn, a strict-grounding persona
    # is fabricating — the reply is withheld. The last alternative is a
    # structural signal rather than a phrase: a vault-shaped file path (e.g.
    # "General/Personal Philosophy.md" in a fabricated "Source:" citation)
    # can only be legitimate here if a retrieval actually produced it, and
    # this regex is only ever consulted when it didn't (see the `not
    # has_sub_agent` guard around its call sites) — so a bare path match is
    # as damning as the wording-based alternatives, without having to
    # enumerate every way a model can dress up an invented note.
    #
    # ADR-124: every call site below now checks
    # `VaultManager.first_unverified_referent` first, which catches a claim
    # naming something real (a real folder, note, or title) regardless of
    # phrasing. This regex remains as the residual catch for the case that
    # check structurally cannot cover: a referent-less claim of authority
    # ("here's a summary of what you wrote") that names nothing checkable at
    # all. Do not grow this list to chase new wordings of a *named* claim —
    # that gap now belongs to the structural check instead.
    _VAULT_CLAIM_RE = re.compile(
        r"(what you (?:wrote|written|noted|said) about|here'?s (?:a |the )?summary of what you|"
        r"your (?:entry|note|journal entry|vault note)\b|in your vault\b|from your vault\b|"
        r"you (?:describe|mention|write about) .{0,40}\bin (?:your|the) (?:vault|journal|notes?)\b|"
        r"[\w][\w \-]*(?:/[\w][\w \-]*)+\.md\b)",
        re.IGNORECASE,
    )
    _NAME_STOP = frozenset(
        {
            "certainly",
            "sure",
            "here",
            "your",
            "yours",
            "the",
            "would",
            "could",
            "sympose",
            "okay",
            "yes",
            "let",
            "what",
            "when",
            "how",
            "and",
            "but",
            "sub",
            "agent",
            "report",
            "task",
            "skills",
            "vault",
            "note",
            "hello",
            "hi",
            "hey",
            "thanks",
            "thank",
            "today",
            "whether",
            "since",
            "well",
            # Contractions are never entities regardless of position - a
            # sentence-boundary check alone misses one that follows a comma
            # ("Yes, I'm here") rather than a full stop. _depossess() strips
            # a trailing 's ('it's' -> 'it') before this set is checked, so
            # an 's-contraction belongs here in its already-stripped form,
            # not as the literal "word's" spelling.
            "i'm",
            "i'll",
            "i've",
            "i'd",
            "you're",
            "you'll",
            "you've",
            "we're",
            "we'll",
            "we've",
            "they're",
            "it",
            "that",
            "there",
            "who",
        }
    )

    @staticmethod
    def _is_full_body_vault_ctx(vault_ctx: str | None) -> bool:
        """Pre-turn `vault_ctx` (VaultManager.resolve_turn_context) comes in two
        shapes: a note's full verbatim body (every such payload carries the
        literal "Exact Content" marker in its header — see vault.py's
        `### Ground-Truth ... (... Exact Content):` returns), or a thin digest
        (a search-results list, a backlink index, the structural manifest) that
        only gives titles/snippets/counts. Only the former is strong enough
        grounding to suspend strict mode's *retrieval-enforcement* fallback
        for the turn — live bug: a "thoughts" search digest (title + one-line
        snippet per note) was enough to turn strict off entirely, and the
        model filled the gap between snippet and full note with an invented
        essay that nothing caught. Citation verification (below) still runs
        on a full body — a real note being available doesn't guarantee the
        model actually used it."""
        return bool(vault_ctx) and "Exact Content" in vault_ctx

    # Shared with SubAgentEngine (sub_agents.py) - see VAULT_PATH_TOKEN_RE's
    # own docstring in vault.py.
    _VAULT_PATH_TOKEN_RE = VAULT_PATH_TOKEN_RE

    @classmethod
    def _vault_ctx_citation_mismatch(cls, clean_text: str, vault_ctx: str | None) -> bool:
        """True when `clean_text` names a vault note path that appears
        nowhere in the ground-truth `vault_ctx` actually injected this turn —
        i.e. the model swapped in an invented path instead of the real one it
        was given. Live bug: handed the real content of
        `Daily/2023/05-May/2023-05-17.md`, gemma4:e4b answered with a
        plausible-looking but entirely fictional `Thoughts/hmmm.md` instead
        of quoting what it actually had. Silent (False) when the reply names
        no path at all — that prose-only case isn't checkable without a
        second model call to compare meaning, which conflicts with Sympose's
        round-trip-frugal design, so it stays a known residual gap rather
        than something this catches."""
        if not vault_ctx:
            return False
        reply_paths = {p.lower() for p in cls._VAULT_PATH_TOKEN_RE.findall(clean_text)}
        if not reply_paths:
            return False
        ctx_paths = {p.lower() for p in cls._VAULT_PATH_TOKEN_RE.findall(vault_ctx)}
        return not (reply_paths & ctx_paths)

    _FILENAME_EXT_RE = re.compile(r"\.(?:md|markdown|txt)$", re.IGNORECASE)

    # Header unique to `VaultManager.get_folder_digest` (vault_folders.py) -
    # a multi-note, metadata-only summary meant to be generalized across,
    # never a single note the reply is expected to quote or name. Distinct
    # from `get_random_sample_notes`' own per-note "Exact Content" header,
    # which still hands over one or two specific notes a reply legitimately
    # should reference by name.
    _FOLDER_DIGEST_MARKER = "High-Density Folder Digest"

    @classmethod
    def _vault_ctx_title_missing(cls, clean_text: str, vault_ctx: str | None) -> bool:
        """True when a real note was handed to the model this turn and its
        reply never mentions that note's own title at all - the residual gap
        `_vault_ctx_citation_mismatch` (above) leaves open by design: a
        reply naming zero paths isn't a mismatch by that check's own logic,
        but zero paths is also exactly what a model saying nothing real at
        all looks like. Live bug, confirmed by repeated live runs: handed a
        real note - any real note, regardless of topic - gemma4:e4b
        narrated a specific, unrelated, sometimes entirely fictional title
        in prose instead of quoting or even referencing what it actually
        had, every single time. Deliberately a presence check, not a
        meaning check (no second model call, same round-trip-frugal
        reasoning as the sibling check) - flags only when NONE of the real
        note(s)' own titles appear anywhere in the reply, so a reply that
        paraphrases around the real title without repeating it verbatim is
        a false negative here, not a false positive; and a short/generic
        stem (under 4 characters) is skipped to keep that rare miss from
        becoming a noisy one.

        Exempts a folder-digest answer (ADR-123) outright - live bug,
        found against a real vault: asked to characterize a whole folder
        ("what kind of things live in Movies/"), a correct answer
        legitimately generalizes across many notes and has no reason to
        name any one of them, but this check couldn't tell that apart from
        the single-note case it was built for and discarded a correct,
        well-grounded answer as if it were the same fabrication this check
        exists to catch."""
        if not vault_ctx:
            return False
        if cls._FOLDER_DIGEST_MARKER in vault_ctx:
            return False
        ctx_paths = cls._VAULT_PATH_TOKEN_RE.findall(vault_ctx)
        stems = {
            cls._FILENAME_EXT_RE.sub("", p.rsplit("/", 1)[-1]).strip().lower()
            for p in ctx_paths
        }
        stems = {s for s in stems if len(s) >= 4}
        if not stems:
            return False
        low = clean_text.lower()
        return not any(re.search(rf"\b{re.escape(s)}\b", low) for s in stems)

    @staticmethod
    def _strip_vault_ctx_headers(vault_ctx: str) -> str:
        """Drops the internal `### Ground-Truth ...` bookkeeping headers from
        a resolved vault context, leaving just the real note body/bodies to
        show the user directly when the model's own retelling of them can't
        be trusted."""
        return re.sub(r"(?m)^### Ground-Truth[^\n]*\n?", "", vault_ctx).strip()

    @staticmethod
    def _ritual_pull_due(
        mem_hit: str | None, ritual_active: bool, clean_input: str
    ) -> bool:
        """True when this turn should (re)fetch a real note for a "pull a
        random note" ritual: either a fresh memory-fact match this turn
        describes the ritual by name (`mem_hit`), or the ritual was already
        engaged on a prior turn (`ritual_active`) and this message repeats
        none of the fact's own wording - a continuation like "let's do
        another one" - so `find_relevant_memory_fact`'s keyword overlap
        won't fire again on its own. These are independent, not either/or:
        a coincidental, unrelated `mem_hit` on a continuation turn (one
        that doesn't itself describe the ritual) must not suppress an
        already-active ritual - only an explicit, distinct vault ask
        (`has_recall_intent`) ends it; that guard applies only to the
        carry-over path, since a fresh fact match needs no such guard
        (this check's original, unguarded behavior)."""
        if mem_hit and VaultManager.describes_random_pull_ritual(mem_hit):
            return True
        return ritual_active and not VaultManager.has_recall_intent(clean_input)

    def _grounding_mode(self, profile: dict[str, Any], target_model: str) -> str:
        """`strict` → the runtime enforces vault retrieval itself; `trust` →
        rely on the model to emit `[SPAWN_SUB_AGENT: vault_read]`. An explicit
        persona `vault_grounding: strict|trust` wins; otherwise `auto` derives it
        from the model (local backend or a localhost `api_base` → strict)."""
        explicit = str(profile.get("vault_grounding", "") or "").strip().lower()
        if explicit in ("strict", "trust"):
            return explicit
        default = (
            str(self.config.get("vault.grounding_default") or "auto").strip().lower()
        )
        if default in ("strict", "trust"):
            return default
        is_local = is_local_backend(target_model, profile.get("api_base", ""))
        return "strict" if is_local else "trust"

    @staticmethod
    def _build_session_history_digest(
        handle: str, exclude_session_id: str | None
    ) -> str:
        """Deterministic, zero-round-trip answer to 'what did we do last
        session?': the persona's own local JSONL history (SessionManager,
        ADR-054) already holds exactly this, so it's injected as ground-truth
        context the same way vault_ctx is — no sub-agent, no extra LLM call.
        Always returns a non-empty block when session_recall intent fires, so
        the model has a definitive answer instead of guessing or defaulting
        to a vault crawl (which is a different store entirely and, per
        `session.exit_behavior`, may hold nothing anyway)."""
        sessions = [
            s
            for s in SessionManager.list_sessions(handle=handle, limit=6)
            if s.get("session_id") != exclude_session_id
        ][:3]
        if not sessions:
            return (
                "### Local Sympose Session History:\n"
                "No prior Sympose session is recorded locally for this persona "
                "yet. This is NOT the same as the Obsidian vault — do not spawn "
                "a vault_read sub-agent for this; just say so."
            )
        lines = [
            f'- "{s.get("title", "Untitled Session")}" — {s.get("relative_time", "")} '
            f'({s.get("turns_count", 0)} turns)'
            for s in sessions
        ]
        return (
            "### Local Sympose Session History (most recent first):\n"
            + "\n".join(lines)
            + "\n\nThis is Sympose's own local conversation history, not the "
            "Obsidian vault — answer from it directly, do not spawn a "
            "vault_read sub-agent for this question."
        )

    @staticmethod
    def _depossess(word: str) -> str:
        return re.sub(r"['’]s?$", "", word).strip()

    @classmethod
    def _entity_guess(
        cls, *texts: str, extra_stop: frozenset[str] | set[str] = frozenset()
    ) -> str:
        """Best-effort name/subject of a recall request across a few candidate
        strings (current message, then recent history), for the strict-grounding
        forced retrieval. Returns '' when nothing looks like a subject.

        `extra_stop` is for names that are never a legitimate recall subject
        in *this* install specifically - the active user and personas, who
        are conversants, not a note topic - resolved dynamically by the
        caller (`chat_stream`) rather than hardcoded here, since any fixed
        set of names would only ever match one install's own user/personas
        and would wrongly suppress a genuine subject with the same name for
        anyone else."""
        stop = cls._NAME_STOP | {s.lower() for s in extra_stop}
        for text in texts:
            if not text:
                continue
            # A recall cue (lower-case mid-sentence) followed by the subject —
            # up to two extra Capitalised words for a full name.
            m = re.search(
                r"\b(?:about|on|regarding|know|knew|mentioned|pull(?: up)?|summari[sz]e|"
                r"entry (?:for|on|about)|note (?:for|on|about))\s+"
                r"([A-Za-z][\w'’-]{2,}(?:\s+[A-Z][\w'’-]{2,}){0,2})",
                text,
            )
            if m:
                cand = cls._depossess(m.group(1).strip().rstrip(".,!?"))
                if cand and cand.lower() not in stop:
                    return cand
            # Fallback: any other Capitalised word — but only mid-sentence.
            # Sentence-initial capitalisation is just English grammar (or a
            # contraction like "I'll"/"I'm"), not an entity signal, and was
            # handing back words like "Hello" or "I'll" from ordinary small
            # talk with no real subject in it at all.
            for cm in re.finditer(r"\b[A-Z][a-zA-Z’'-]{2,}\b", text):
                start = cm.start()
                if start == 0 or re.search(r"[.!?]\s$", text[max(0, start - 2) : start]):
                    continue
                d = cls._depossess(cm.group(0))
                if d and d.lower() not in stop:
                    return d
        return ""
