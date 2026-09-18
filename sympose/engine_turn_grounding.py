"""
Calling the model and enforcing ADR-124 grounding on what comes back:
streaming with strict-mode holdback so a fabricated reply can be caught
before the user sees it, resolving the likely subject of an ungrounded
claim, and applying whichever enforcement check fires (`verify_ctx` for a
misquoted/ignored real note, `strict` for an answer given with no
retrieval at all).

Split out of engine_turn_pipeline.py per ADR-125's own note that that
cluster would need a second pass once it was out of engine.py and easier
to judge; every method here is unchanged from its prior home. Kept as one
tightly-coupled trio rather than split further — the call, the
strict-mode holdback (`held`/`hold_stream`), and the enforcement that
decides what to release all thread the same in-flight generator state.
`TurnPipelineMixin(..., TurnGroundingMixin, ...)` in
engine_turn_pipeline.py composes this in, so engine.py's own class
declaration doesn't need to change. Depends on `self.pm`, `self.config`,
plus sibling methods from `GroundingHelpersMixin`/`PersonaEngine`
(`_build_kwargs`, `_visible_stream`, `_entity_guess`, `_VAULT_CLAIM_RE`,
`_vault_ctx_citation_mismatch`, `_vault_ctx_title_missing`,
`_strip_vault_ctx_headers`), all resolved normally through the MRO.
"""

import logging
import re
from collections.abc import Callable
from typing import Any

import litellm

from sympose.actions import ActionProcessor
from sympose.vault import VaultManager

log = logging.getLogger(__name__)


class TurnGroundingMixin:
    def _call_and_stream_model(
        self,
        call_model: str,
        routed_local: bool,
        profile: dict[str, Any],
        active_messages: list[dict[str, str]],
        target_model: str,
        stream_val: bool,
        hold_stream: bool,
        held: list[str],
    ):
        """Calls the model, falling back from a failed local route to
        `target_model`, and streams pieces through `_visible_stream` —
        buffered into `held` for a strict-grounding persona instead of
        yielded live, so a fabricated reply can still be caught before the
        user sees it. Returns the complete un-filtered model output (for
        downstream action-tag parsing) as this generator's return value."""
        kwargs = self._build_kwargs(
            call_model, profile, active_messages, stream=stream_val
        )
        if routed_local:
            kwargs["max_tokens"] = int(
                self.config.get("performance.local_simple_max_tokens")
            )
        try:
            response = litellm.completion(**kwargs)
        except Exception:
            if not routed_local:
                raise
            log.debug(
                "Local-routed call to %s failed, falling back to %s",
                call_model,
                target_model,
            )
            call_model, routed_local = target_model, False
            kwargs = self._build_kwargs(
                call_model, profile, active_messages, stream=stream_val
            )
            response = litellm.completion(**kwargs)
        sink: list[str] = []
        for piece in self._visible_stream(response, sink):
            # strict-grounding personas hold the model's text until we know
            # whether it fabricated an un-retrieved vault answer, or (when
            # a real note was already given) cited a different one than
            # the one it actually has.
            if hold_stream:
                held.append(piece)
            else:
                yield piece
        return sink[0] if sink else ""

    def _resolve_strict_grounding_subject(
        self,
        profile: dict[str, Any],
        clean_input: str,
        clean_text: str,
        history: list[dict[str, str]],
    ) -> str:
        """Best-effort vault-recall subject for a strict-grounding turn with
        no retrieval yet, tried in order: a recall lead-in in the user's own
        message; a real vault referent (or an offer-language match) on the
        prior assistant turn when this one is an affirmed continuation; a
        real referent or `_VAULT_CLAIM_RE` match in the reply itself. ''
        when nothing is worth fetching. The real-referent checks are
        ADR-124's structural, index-backed signal — it catches a claim
        naming something real (e.g. "the People directory") regardless of
        phrasing, which none of the phrase-based alternatives here can.

        Deliberately NOT checking `clean_input` itself for a bare real
        referent with no recall lead-in at all: ADR-124 explicitly rejected
        that as unscoped (a vault note titled "Coffee" would turn "Coffee is
        great this morning" into a spurious vault fetch). The lead-in check
        above and the two checks below stay scoped to cases the model or the
        conversation already treats as vault-shaped."""
        # The active user and every persona's own name/handle are never
        # themselves a recall subject - resolved fresh per install rather
        # than a fixed list, so this holds for whichever names this
        # persona hub actually has.
        not_a_subject = {self.pm.get_primary_user_name().lower()} | {
            n.lower()
            for p in self.pm.list_personas()
            for n in (p.get("handle", ""), p.get("name", ""))
            if n
        }
        prev_asst = next(
            (
                m["content"]
                for m in reversed(history)
                if m.get("role") == "assistant"
            ),
            "",
        )
        prev_user = next(
            (m["content"] for m in reversed(history) if m.get("role") == "user"),
            "",
        )
        affirm = bool(
            re.match(
                r"^(yes|yep|yeah|sure|ok(ay)?|please( do)?|go ahead|do it|go on|"
                r"continue|just summari[sz]e|summari[sz]e it)\b",
                clean_input,
                re.IGNORECASE,
            )
        )
        subj, had_leadin = VaultManager._extract_recall_subject(clean_input)
        if not (had_leadin or VaultManager.has_recall_intent(clean_input)):
            subj = ""
        if not subj and affirm:
            structural_prev = VaultManager.first_unverified_referent(
                prev_asst, profile, extra_stop=not_a_subject
            )
            if structural_prev or re.search(
                r"\b(pull|retriev|check|look (up|at)|find|fetch|summari[sz]e)\b.{0,60}\b(entry|note|vault|journal)\b",
                prev_asst,
                re.IGNORECASE,
            ):
                subj = structural_prev or self._entity_guess(
                    prev_asst, prev_user, extra_stop=not_a_subject
                )
        if not subj:
            # The claim just made is in clean_text itself (e.g. "here's your
            # entry about X") — search it first, not the *previous* turn's
            # assistant text, which has no bearing on this claim and can
            # hand back an unrelated word from earlier small talk.
            # ADR-124.3 — a real vault name in the reply (structural) is as
            # damning as the phrase-based claim check when nothing was
            # retrieved this turn: it catches "this one is from the People
            # directory" the same way it catches a fabricated filename,
            # because it checks what's named against what's real rather
            # than matching wording nobody anticipated.
            structural_claim = VaultManager.first_unverified_referent(
                clean_text, profile, extra_stop=not_a_subject
            )
            if structural_claim or self._VAULT_CLAIM_RE.search(clean_text):
                subj = structural_claim or self._entity_guess(
                    clean_text, clean_input, prev_user, extra_stop=not_a_subject
                )
        return subj

    def _apply_grounding_and_stream_result(
        self,
        handle: str,
        profile: dict[str, Any],
        clean_input: str,
        complete_text: str,
        vault_ctx: str | None,
        strict: bool,
        verify_ctx: bool,
        hold_stream: bool,
        held: list[str],
        history: list[dict[str, str]],
        on_sub_agent_progress: Callable[[str], None] | None,
    ):
        """Parses action tags out of the raw model output, then runs
        whichever grounding-enforcement check applies — `verify_ctx` and
        `strict` are mutually exclusive by construction (see `chat_stream`)
        — and yields whatever survives to show the user. `verify_ctx`
        catches a real note being misquoted or ignored; `strict` catches an
        answer given with no retrieval at all, using both the phrase-based
        `_VAULT_CLAIM_RE` and the structural, index-backed check from
        ADR-124. Returns (clean_text, badges, has_sub_agent, has_retrieval,
        was_forced) as this generator's return value."""
        clean_text, badges = ActionProcessor.execute_actions(
            self.pm,
            handle,
            complete_text,
            user_prompt=clean_input,
            on_progress=on_sub_agent_progress,
        )
        has_sub_agent = any(
            "Sub-Agent" in b or "Live Web Search Report" in b for b in badges
        )
        has_retrieval = has_sub_agent or any("Web Search" in b for b in badges)

        forced_answer = None
        if verify_ctx and not has_sub_agent and (
            self._vault_ctx_citation_mismatch(clean_text, vault_ctx)
            or self._vault_ctx_title_missing(clean_text, vault_ctx)
        ):
            # A real note was handed to the model this turn and it either
            # named a different one instead of quoting what it actually
            # had, or never referenced the real one at all - discard the
            # invented reply and show the real note directly rather than
            # trusting a second attempt to do better. Phrased as an honest
            # verification gap ("couldn't fully verify"), not an assertion
            # that the model was wrong - this still can't tell a genuine
            # fabrication from a real answer phrased in a way this check
            # doesn't recognize, so it shouldn't claim more certainty than
            # it has either way (same reasoning discussed with damiro for
            # why the digest case above is exempted outright, applied here
            # to the wording for the cases still worth catching).
            clean_text = (
                "I couldn't fully verify that against what's actually on "
                "file, so here's the exact note instead:\n\n"
                + self._strip_vault_ctx_headers(vault_ctx or "")
            )
            held = [clean_text]
        elif strict and not has_sub_agent:
            # The model neither had pre-turn context nor spawned a sub-agent.
            # If a vault subject is in play, retrieve it ourselves; if it is
            # clearly reporting vault content anyway, withhold the guess.
            subj = self._resolve_strict_grounding_subject(
                profile, clean_input, clean_text, history
            )
            if subj:
                _, fb = ActionProcessor.execute_actions(
                    self.pm,
                    handle,
                    f"[SPAWN_SUB_AGENT: vault_read | {subj}]",
                    user_prompt=clean_input,
                    on_progress=on_sub_agent_progress,
                )
                if any("Sub-Agent" in b for b in fb):
                    badges = fb + badges
                    has_sub_agent = has_retrieval = True
                    clean_text = ""  # discard the model's un-retrieved answer
            elif self._VAULT_CLAIM_RE.search(clean_text):
                forced_answer = (
                    "I haven't actually pulled that from your vault yet — tell me the "
                    "note or the name and I'll read it for you."
                )
                clean_text = forced_answer

        if hold_stream:
            # Emit what survived the check: the candid line, or the model's
            # own text when it did not need forcing.
            if forced_answer is not None:
                yield forced_answer
            elif not (has_sub_agent and not "".join(held).strip()):
                lead = "".join(held) if clean_text else ""
                if lead:
                    yield lead

        return clean_text, badges, has_sub_agent, has_retrieval, forced_answer is not None
