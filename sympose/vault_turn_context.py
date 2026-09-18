"""
Pre-inference vault retrieval: `resolve_turn_context`, the orchestrator
that decides whether — and from where — a turn gets real, ground-truth
vault content before the model ever answers, plus everything it and the
"pull a random note" ritual depend on (the conversational-recall search
helpers, the ritual's own folder-scoped sampler, single-note refresh).

Split out of vault.py per ADR-125 purely to keep that file under this
project's own size guidance. `resolve_turn_context` itself was previously
kept in vault.py specifically to avoid threading its roughly-a-dozen
VaultManager dependencies through explicit parameters (see
vault_recall.py's own docstring for that history) — this module resolves
that by staying a mixin: `VaultManager(TurnContextMixin, ...)` means
`cls.read_note`, `cls.get_manifest`, `cls.search`, and everything else
here keep resolving through the normal MRO, exactly as if this code had
never left vault.py. Every method below is unchanged from its prior home;
this is a pure move, not a rewrite.
"""

import logging
import os
import re
from typing import Any

from sympose import vault_grounding, vault_recall

log = logging.getLogger(__name__)


class TurnContextMixin:
    @classmethod
    def resolve_ritual_random_pull(
        cls, profile: dict[str, Any], message: str
    ) -> str | None:
        """Live bug: "let's play our favorite game" doesn't match
        `resolve_turn_context`'s own sample-request phrasing ("random",
        "surprise me", "give me a"...), so its structural retrieval never
        fires for it even when the persona's own memory says the game IS a
        random-note pull - leaving the model to invent a plausible-sounding
        note title instead of performing a real one. Called only once a
        matched memory fact has already been confirmed (via
        `describes_random_pull_ritual`) to describe exactly this ritual.
        Folder-scopes to any discovered folder named in the message, the
        same way `resolve_turn_context`'s case 7 does; otherwise samples
        across the whole vault a persona has full access to."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return None
        for folder_name in cls.get_discovered_folders(profile):
            stem = folder_name.rstrip("s")
            if re.search(rf"\b{re.escape(stem)}\w*\b", message, re.IGNORECASE):
                return cls.get_random_sample_notes(profile, folder_name, count=1) or None
        if any(os.path.realpath(d) == os.path.realpath(mv) for d in allowed_dirs):
            return (
                cls.get_random_sample_notes(profile, os.path.basename(mv), count=1)
                or None
            )
        return None

    @classmethod
    def _recall_hit(
        cls,
        profile: dict[str, Any],
        cand: str,
        target_folder: str | None = None,
        require_confident: bool = False,
    ) -> str | None:
        """Search one candidate term for the conversational-recall fallback.
        A single result — or a clear title match on the first hit — returns the
        note's *full verbatim body* (the strongest possible grounding payload);
        anything broader returns the ranked digest so the model can pick.

        `require_confident` drops that digest fallback entirely: the caller
        passes it for `_recall_candidates`' *decomposed single-token* tries
        (a multi-word phrase whittled down to its longest leftover words),
        never for the original phrase itself. Live bug: "play our favorite
        game" (no folder-scoped match) decomposed to the single word
        "favorite", which matched five unrelated notes' body text and was
        accepted as a digest anyway - a common English word loosely
        appearing in several notes isn't the same evidence as the user's own
        multi-word phrase matching broadly; only a strong single/title match
        earns trust once the subject has been cut down to one bare word."""
        results = cls.search_structured(profile, cand, target_folder=target_folder)
        if not results:
            return None
        top = results[0]
        if len(results) == 1 or top.get("match_type") == "title":
            body = cls.read_note(
                profile, top.get("rel_path") or top.get("file_name", "")
            )
            if body and not body.startswith(("⚠️", "Error reading", "Note `")):
                loc = f" in `{target_folder}/`" if target_folder else ""
                return (
                    f"### Ground-Truth Sandboxed Vault Note (`{top.get('rel_path')}` "
                    f"— Exact Content, matched '{cand}'{loc}):\n{body[:3500]}"
                )
        if require_confident:
            return None
        digest = cls.format_search_digest(cand, results)
        loc = f" in `{target_folder}/`" if target_folder else ""
        return f"### Ground-Truth Vault Search Results for '{cand}'{loc}:\n{digest}"

    # Matches the label on a single-file "Ground-Truth ... Exact Content" block
    # built by resolve_turn_context below. Used only to re-read that same note
    # fresh before reusing it on a later turn — see refresh_note_context.
    _SANDBOXED_NOTE_RE = re.compile(
        r"^### Ground-Truth Sandboxed Vault Note \(`([^`]+)` - Exact Content\):\n"
    )

    @classmethod
    def refresh_note_context(cls, profile: dict[str, Any], cached_text: str) -> str:
        """Re-reads a cached single-note vault context from disk before reuse
        on a later turn. `active_vault_ctx` in the engine carries a resolved
        context forward across turns that don't themselves trigger a fresh
        recall — but the note may have been edited since it was first read,
        and replaying the frozen text would silently contradict the
        "Ground-Truth"/"Exact Content" label it carries. Falls back to the
        cached text unchanged for anything that isn't a single-note read
        (manifest/backlink/search digests span multiple notes and are lower
        risk) or if the re-read fails."""
        m = cls._SANDBOXED_NOTE_RE.match(cached_text)
        if not m:
            return cached_text
        note_ref = m.group(1)
        fresh = cls.read_note(profile, note_ref)
        if not fresh or fresh.startswith("Note `") or fresh.startswith("⚠️") or fresh.startswith("Error reading"):
            return cached_text
        return f"### Ground-Truth Sandboxed Vault Note (`{note_ref}` - Exact Content):\n{fresh}"

    @classmethod
    def resolve_turn_context(cls, profile: dict[str, Any], message: str) -> str | None:
        """Skill-gated, structure-agnostic pre-inference retrieval conforming
        to skills/vault_read. Tries each retrieval case below in order,
        cases 1b-4 first (each self-contained), then the subject/chrono/
        sample-aware cases 5-8 (which share prep computed once here) -
        returns the first one that finds something real, None if none did."""
        # 1. Skill Permission Gate: only proceed if persona is authorized for vault recall
        if not cls.has_vault_skill(profile):
            return None

        msg = message.strip()
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return None

        hit = (
            cls._resolve_manifest_digest_case(msg)
            or cls._resolve_backlink_case(profile, msg)
            or cls._resolve_quoted_title_case(profile, msg)
            or cls._resolve_explicit_note_read_case(profile, msg)
        )
        if hit:
            return hit

        subject, had_leadin, is_chrono_query, is_sample_request = cls._recall_prep(msg)
        has_intent = any(k in msg.lower() for k in vault_recall.search_triggers())

        hit = cls._resolve_chrono_sample_case(
            profile, mv, is_chrono_query, is_sample_request, subject
        )
        if hit:
            return hit

        hit = cls._resolve_year_chrono_case(profile, msg, is_chrono_query)
        if hit:
            return hit

        hit, folder_scope_matched = cls._resolve_folder_scope_case(
            profile, msg, subject, is_sample_request
        )
        if hit:
            return hit

        hit = cls._resolve_real_referent_case(profile, msg, folder_scope_matched)
        if hit:
            return hit

        hit = cls._resolve_conversational_fallback_case(
            profile, subject, had_leadin, has_intent, folder_scope_matched
        )
        if hit:
            return hit

        return cls._resolve_possessive_miss_case(profile, msg)

    @classmethod
    def _resolve_manifest_digest_case(cls, msg: str) -> str | None:
        """Case 1b - vault structure map (ADR-078). Any "how big / how
        organised / how many / what's in / stats" question about the vault
        gets the disk-true map — cheap, always accurate, no walk. Skipped
        when the message names a subject (that's a search, not a shape
        question). Inert unless `vault.manifest.enabled`; structure only."""
        if (
            re.search(
                r"\b(vault|obsidian|journal|(?:my|our|the)\s+notes?)\b",
                msg,
                re.IGNORECASE,
            )
            and re.search(
                r"\b(structure|structured|organi[sz]\w+|hierarch\w+|layout|"
                r"topolog\w+|folders?|sub-?folders?|breakdown|stats?|status|"
                r"summary|overview|snapshot|inventory|shape|size|"
                r"how many|how much|how big|how large|how'?s|hows|"
                r"what'?s in|state of|count)\b",
                msg,
                re.IGNORECASE,
            )
            and not re.search(r"\babout\b|\bregarding\b|[\"'][^\"']{2,}[\"']", msg)
        ):
            manifest = cls.get_manifest()
            if manifest and manifest.get("nodes"):
                return cls.format_manifest_digest(manifest)
        return None

    @classmethod
    def _resolve_backlink_case(cls, profile: dict[str, Any], msg: str) -> str | None:
        """Case 2 - wikilink & backlink queries ("what notes link to
        [[OAuth]]?", "backlinks for Architecture")."""
        bl_match = re.search(
            r"(?:what\s+(?:notes\s+)?(?:link\s+to|reference)|who\s+(?:links\s+to|references)|backlinks?\s+(?:for|to|of)?)\s+(?:\[\[)?([a-zA-Z0-9_\-\s/\.]+?)(?:\]\])?(?:\?|$|\.|\n)",
            msg,
            re.IGNORECASE,
        )
        if bl_match:
            bl_target = bl_match.group(1).strip()
            if len(bl_target) >= 2:
                digest = cls.get_backlinks_digest(profile, bl_target)
                if digest and not digest.startswith("No backlinks found"):
                    return f"### Ground-Truth Vault Backlink Index for `[[{bl_target}]]`:\n{digest}"
        return None

    @classmethod
    def _resolve_quoted_title_case(cls, profile: dict[str, Any], msg: str) -> str | None:
        """Case 3 - quoted note title lookup (e.g. "If I Stay", 'If I Stay')."""
        for q_match in re.findall(r"[\"']([^\"']+)[\"']", msg):
            q_clean = q_match.strip()
            if len(q_clean) >= 2:
                content = cls.read_note(profile, q_clean)
                if (
                    content
                    and not content.startswith("Note `")
                    and not content.startswith("⚠️")
                ):
                    return f"### Ground-Truth Sandboxed Vault Note (`{q_clean}` - Exact Content):\n{content}"
        return None

    @classmethod
    def _resolve_explicit_note_read_case(
        cls, profile: dict[str, Any], msg: str
    ) -> str | None:
        """Case 4 - explicit note reading requests ("read note X", "look at
        note X")."""
        rd = re.search(
            r"(?:read|open|check|look\s+at|show\s+me)\s+(?:the\s+)?note\s+([a-zA-Z0-9_\-/\.\s]+(?:\.md|\.markdown|\.txt|[a-zA-Z0-9]))",
            msg,
            re.IGNORECASE,
        )
        if rd:
            note_target = rd.group(1).strip()
            c = cls.read_note(profile, note_target)
            if c and not c.startswith("Note `") and not c.startswith("⚠️"):
                return f"### Ground-Truth Sandboxed Vault Note (`{note_target}` - Exact Content):\n{c}"
        return None

    @classmethod
    def _recall_prep(cls, msg: str) -> tuple[str, bool, bool, bool]:
        """Shared prep for cases 5, 7 and 8: the conversational-recall
        subject (cleaned of low-confidence noise), and the chrono/sample
        intent flags. Returns (subject, had_leadin, is_chrono_query,
        is_sample_request)."""
        # Subject of a conversational recall request ("Dylan's people entry" ->
        # "dylan people"), extracted once: it both gates the random sampler
        # below (a named subject is never a request for a *random* note) and
        # drives the case-8 fallback search.
        subject, had_leadin = cls._extract_recall_subject(msg)
        # A low-confidence guess (no explicit lead-in) shorter than a real
        # search term is noise, not a target — live bug: "g?" (shorthand for
        # "go") survived stopword-trimming as the winning fallback clause and
        # blocked the random-sample path below just as effectively as a
        # whole invented topic would have. Case 8 already required length
        # >= 3 for its own fallback search; applying that same bar here too
        # closes the same gap for the gates above it.
        if subject and not had_leadin and len(subject) < 3:
            subject = ""

        # 5. Chronological & Daily Journal Intent (Structure-Agnostic)
        is_chrono_query = bool(
            re.search(
                r"\b(daily|journal|diary|reflection|reflections|log|logs|day's\s+note|entry|entries)\b",
                msg,
                re.IGNORECASE,
            )
        )
        # Only an *explicit* ask for an arbitrary note — "pull"/"grab"/"get"/
        # "pick" alone are not it ("pull up Dylan's entry" names a target).
        sample_match = re.search(
            r"\b(?:random(?:ly)?|randam|rnd|surprise\s+me|a\s+random|any\s+(?:random\s+)?(?:one|note|entry|day)|"
            r"some\s+(?:random\s+)?(?:note|entry|day)|(?:pick|choose|grab|pull\s+up|show|give)\s+(?:me\s+)?(?:a|an|one|any)\b|"
            r"one\s+of\s+(?:my|the|our)|whatever\s+comes\s+up)\b",
            msg,
            re.IGNORECASE,
        )
        is_sample_request = bool(sample_match)

        # A low-confidence subject guess (no explicit recall lead-in like
        # "pull up notes on X") that comes from an earlier sentence than the
        # one actually making the random-note ask is filler, not a named
        # target — live bug: "hmmm.. not really what I expected. It should
        # be a random note from the thoughts folder" guessed the subject
        # "hmmm" from the reflex-reaction opener, which then blocked the
        # random-sample path below and sent an unrelated word to a vault-wide
        # search instead. Checked by sentence co-occurrence rather than an
        # enumerable filler-word list, so it generalises to any interjection.
        # A confident lead-in match is never cleared this way even if the
        # message also happens to mention "random" elsewhere.
        if subject and not had_leadin and sample_match:
            request_sentence = next(
                (
                    s
                    for s in re.split(r"[.?!]+\s+", msg)
                    if sample_match.group(0).lower() in s.lower()
                ),
                "",
            )
            if subject not in request_sentence.lower():
                subject = ""

        return subject, had_leadin, is_chrono_query, is_sample_request

    @classmethod
    def _resolve_chrono_sample_case(
        cls,
        profile: dict[str, Any],
        mv: str,
        is_chrono_query: bool,
        is_sample_request: bool,
        subject: str,
    ) -> str | None:
        """The rest of case 5 - an explicit "random daily/journal entry" ask
        with no named subject gets one truly random chronological note."""
        if is_chrono_query and is_sample_request and not subject:
            chrono_notes = cls.find_chronological_notes(profile)
            if chrono_notes:
                import random

                selected_fp = random.choice(chrono_notes)
                rel = os.path.relpath(selected_fp, mv)
                try:
                    with open(selected_fp, "r", encoding="utf-8", errors="replace") as f:
                        body = f.read().strip()
                    if body:
                        return f"### Ground-Truth Sandboxed Vault Note (`{rel}` - Exact Content):\n{body[:3000]}"
                except Exception as e:
                    log.debug(
                        "Failed to read sampled chronological note %s: %s", rel, e
                    )
        return None

    @classmethod
    def _resolve_year_chrono_case(
        cls, profile: dict[str, Any], msg: str, is_chrono_query: bool
    ) -> str | None:
        """Case 6 - year-based chronological queries ("2020 journal entry")."""
        yr = re.search(r"\b(201\d|202\d|19\d\d)\b", msg)
        if yr and is_chrono_query:
            res = cls.search(profile, yr.group(1))
            if (
                res
                and not res.startswith("No notes found")
                and "not configured" not in res
            ):
                return (
                    f"### Ground-Truth Vault Search Results for '{yr.group(1)}':\n{res}"
                )
        return None

    @classmethod
    def _resolve_folder_scope_case(
        cls,
        profile: dict[str, Any],
        msg: str,
        subject: str,
        is_sample_request: bool,
    ) -> tuple[str | None, bool]:
        """Case 7 - dynamic real-directory discovery & sampling (zero
        hardcoding). Returns (hit, folder_scope_matched) - the latter is set
        as soon as the message names a real folder, even when nothing under
        it actually resolves, so case 8 knows not to re-broaden the same
        request to the whole vault.

        ADR-123.4: gated purely on a real folder name appearing in the
        message, not on `has_intent` (a fixed recall-keyword list) - a
        write-shaped message ("add Dylan's birthday to People/") names a
        real folder just as validly as a recall-shaped one, and the
        folder-name match is already structural (it's checked against
        `get_discovered_folders`' real directory names, not an enumerated
        vocabulary), so it doesn't need a keyword gate in front of it the
        way the vault-wide fallback in case 8 still does - see that case's
        own docstring for why *that* one stays conservative."""
        discovered_dirs = cls.get_discovered_folders(profile)
        folder_scope_matched = False
        if discovered_dirs:
            for folder_name, folder_path in discovered_dirs.items():
                f_stem = folder_name.rstrip("s")
                if re.search(rf"\b{re.escape(f_stem)}\w*\b", msg, re.IGNORECASE):
                    folder_scope_matched = True
                    if is_sample_request and not subject:
                        samples = cls.get_random_sample_notes(
                            profile, folder_name, count=1
                        )
                        if samples:
                            return (
                                f"### Ground-Truth Selected Note from `{folder_name}/` (Exact Content):\n{samples}",
                                folder_scope_matched,
                            )
                    if re.search(
                        r"\b(scan|analyze|summarize|all|overview|connections?|access)\b",
                        msg,
                        re.IGNORECASE,
                    ):
                        return cls.get_folder_digest(profile, folder_name), folder_scope_matched
                    # A named subject alongside the folder ("Dylan's People entry")
                    # means search *that* inside the folder, not list the folder.
                    if subject:
                        hit = cls._recall_hit_within_folder(profile, subject, f_stem, folder_name)
                        if hit:
                            return hit, folder_scope_matched
                    res = cls.search(profile, folder_name, target_folder=folder_name)
                    if (
                        res
                        and not res.startswith("No notes found")
                        and "not configured" not in res
                    ):
                        return (
                            f"### Ground-Truth Vault Search Results for '{folder_name}':\n{res}",
                            folder_scope_matched,
                        )
        return None, folder_scope_matched

    @classmethod
    def _recall_hit_within_folder(
        cls, profile: dict[str, Any], subject: str, f_stem: str, folder_name: str
    ) -> str | None:
        """Searches `subject` scoped to `folder_name`, trying progressively
        narrower candidates (see `_recall_candidates`) until one resolves
        confidently. Split out of `_resolve_folder_scope_case` (case 7)
        purely to keep that dispatcher under this project's own complexity
        budget - no behavior of its own beyond the loop it replaces."""
        for i, st in enumerate(cls._recall_candidates(subject, drop=f_stem)):
            hit = cls._recall_hit(
                profile, st, target_folder=folder_name, require_confident=i > 0
            )
            if hit:
                return hit
        return None

    @classmethod
    def _resolve_real_referent_case(
        cls, profile: dict[str, Any], msg: str, folder_scope_matched: bool
    ) -> str | None:
        """Case 7.5 (ADR-123.5) - the vault is ground truth: a message
        naming something real (a note's filename stem or frontmatter
        title, not just a folder name) gets that note surfaced, with no
        recall-keyword or lead-in required. This is ADR-123.4's real-name
        gate generalized beyond folders, reusing
        `VaultManager.first_unverified_referent` (ADR-124's structural
        referent index, built to catch the model's own replies naming
        something real, applied here to the *inbound* message instead) -
        the same mechanical fact-check, run in the other direction.

        Skipped once a folder name already matched (case 7 already
        searched that scope) - same guard `_resolve_conversational_fallback_case`
        uses, for the same reason: re-running an unscoped lookup after a
        folder-scoped one already ran risks surfacing an unrelated
        vault-wide hit for a message that named a specific folder.

        Reads the confirmed candidate directly via `read_note` (the same
        resolution case 3 already trusts for a quoted title) instead of
        `_recall_hit`'s ranked-search path - live bug, found against a
        real vault: an ordinary sentence-initial common word ("Life is
        good today.") can itself be a stub note's exact name somewhere in
        an 800-note vault (a near-empty placeholder sitting in a catch-all
        folder), and a *ranked* search for that word matches on loose
        body-text relevance rather than the specific note the referent
        check just confirmed - it surfaced an unrelated Quotes/ note that
        merely mentioned the word, not the confirmed one. A direct read
        has no such ranking step: it either returns that exact note's own
        content, or nothing (an empty stub correctly yields nothing to
        show, rather than a wrong substitute).

        Matches case-insensitively (`real_referent_mentioned`, not
        `first_unverified_referent`) - damiro doesn't capitalize proper
        nouns in casual chat, so a check that only fired on Title Case
        would miss most of his own messages naming something real."""
        if folder_scope_matched:
            return None
        candidate = cls.real_referent_mentioned(msg, profile)
        if not candidate:
            return None
        content = cls.read_note(profile, candidate)
        if content and not content.startswith(("⚠️", "Error reading", "Note `")):
            return f"### Ground-Truth Sandboxed Vault Note (`{candidate}` - Exact Content):\n{content}"
        return None

    @classmethod
    def _resolve_possessive_miss_case(
        cls, profile: dict[str, Any], msg: str
    ) -> str | None:
        """Case 9 (ADR-123.5, miss-surfacing) - the last resort, run only
        once every retrieval case above has already failed to find real
        content. A possessive mention ("Marco's birthday", "dylan's
        school") is a capitalization-independent signal that the speaker
        is naming a specific thing, not just using an ordinary word -
        deliberately narrower than flagging every unmatched word or
        capitalized run, which would report a "miss" on nearly every
        sentence (see ADR-123.5's Implementation notes for why that was
        rejected). When no possessive mention in the message resolves to
        anything real, hands the model a plain fact - not a decision -
        about the first one: what to do with a confirmed miss (nothing,
        ask the user, offer to note it down) is left entirely to the
        model's own judgment of the conversation."""
        real_referents = cls.real_vault_referents(profile)
        if not real_referents:
            return None
        for name in vault_grounding.possessive_mentions(msg):
            if name.lower() not in real_referents:
                return f"### Vault Check: no real vault entry found for '{name}'."
        return None

    @classmethod
    def _resolve_conversational_fallback_case(
        cls,
        profile: dict[str, Any],
        subject: str,
        had_leadin: bool,
        has_intent: bool,
        folder_scope_matched: bool,
    ) -> str | None:
        """Case 8 - conversational recall fallback — search the extracted
        subject, retrying progressively narrower so a multi-word phrase that
        substring-matches nothing still surfaces its salient notes. Skipped
        when the message already named a real folder (case 7 just tried it,
        scoped, and found nothing confident there) - live bug: re-running
        the same decomposed candidates unscoped let "bored" (from "I'm
        bored, let's play...") match an unrelated Quotes/ note vault-wide,
        silently dropping the folder the user actually asked for."""
        if (
            (has_intent or had_leadin)
            and subject
            and len(subject) >= 3
            and not folder_scope_matched
        ):
            for i, cand in enumerate(cls._recall_candidates(subject)):
                hit = cls._recall_hit(profile, cand, require_confident=i > 0)
                if hit:
                    return hit
        return None

    @classmethod
    def _recall_candidates(cls, subject: str, drop: str = "") -> list[str]:
        """Ordered search terms for a recall subject: the full phrase first, then
        its most-specific single tokens (longest, then earliest), then the
        de-pluralised stem of each so an apostrophe-less possessive ('dylans' ->
        'dylan') still matches. `drop` removes one token (e.g. the folder name)."""
        return vault_recall.recall_candidates(subject, drop)
