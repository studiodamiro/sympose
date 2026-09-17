"""
Finishing a chat turn once grounding enforcement has decided what survives:
trimming the reply down to its pre-retrieval-tag lead-in, running a second
grounded synthesis pass over a sub-agent's report, emitting badges, and
persisting the turn to history/session/memory-extraction.

Split out of engine_turn_pipeline.py per ADR-125's own note that that
cluster would need a second pass once it was out of engine.py and easier
to judge; every method here is unchanged from its prior home.
`TurnPipelineMixin(..., TurnFinalizeMixin)` in engine_turn_pipeline.py
composes this in, so engine.py's own class declaration doesn't need to
change. Depends on `self._lock`, `self.histories`, `self.max_turns`,
`self.archivist`, and sibling methods from `GroundingHelpersMixin`
(`_RETRIEVAL_TAG_RE`) and `TurnGroundingMixin` (`_build_kwargs`), all
resolved normally through the MRO.
"""

import logging
import re
from typing import Any

import litellm

from sympose.actions import ActionProcessor
from sympose.sessions import SessionManager

log = logging.getLogger(__name__)


class TurnFinalizeMixin:
    def _finalize_reply_text(
        self,
        complete_text: str,
        clean_text: str,
        badges: list[str],
        has_retrieval: bool,
        was_forced: bool,
    ) -> tuple[str, str]:
        """When a retrieval tag ran, trims `clean_text` down to the model's
        pre-tag lead-in (up to the first tag, minus any fabricated note
        body) — the badges/synthesis that follow supply the real ground
        truth, so the model's own post-tag guess is dropped rather than
        shown as if it were the retrieved answer. Returns (clean_text,
        assistant_record)."""
        if has_retrieval and not was_forced:
            m = self._RETRIEVAL_TAG_RE.search(complete_text)
            lead = complete_text[: m.start()] if m else clean_text
            lead = ActionProcessor.strip_action_tags(lead)
            clean_text = re.split(
                r"\n\s*(?:#{1,6}\s|>\s|-{3,}\s*$|```)", lead, maxsplit=1
            )[0].strip()
        assistant_record = (
            clean_text + ("\n\n" + "\n".join(badges) if badges else "")
        ).strip()
        return clean_text, assistant_record

    def _synthesize_sub_agent_reply(
        self,
        profile: dict[str, Any],
        active_messages: list[dict[str, str]],
        assistant_record: str,
        target_model: str,
    ) -> str:
        """One more model pass, directed to use ONLY the sub-agent report
        (already folded into `assistant_record`) as ground truth. Returns
        '' on any failure — network error or an empty reply — so the
        caller just keeps the report/badges as the final answer either
        way."""
        synth_msgs = list(active_messages) + [
            {"role": "assistant", "content": assistant_record},
            {
                "role": "user",
                "content": "[System Directive: Using ONLY the report above as ground truth, give the user the direct answer. Quote note text verbatim; do not add any detail that is not in the report.]",
            },
        ]
        try:
            synth_resp = litellm.completion(
                **self._build_kwargs(target_model, profile, synth_msgs, stream=True)
            )
            return "".join(
                c.choices[0].delta.content or ""
                for c in synth_resp
                if c.choices[0].delta.content
            ).strip()
        except Exception as e:
            log.debug("Forced synthesis stream failed: %s", e)
            return ""

    def _emit_badges_and_synthesis(
        self,
        profile: dict[str, Any],
        active_messages: list[dict[str, str]],
        badges: list[str],
        assistant_record: str,
        has_sub_agent: bool,
        target_model: str,
    ):
        """Yields the badges line (if any), then — when a sub-agent ran — a
        second grounded synthesis pass that quotes its report verbatim (see
        actions.py READ_NOTE for where that verbatim text comes from).
        Returns the (possibly synthesis-augmented) assistant_record as this
        generator's return value, for session persistence."""
        if badges:
            yield "\n\n" + "\n".join(badges)

        if has_sub_agent:
            yield "\n\n"
            synth_reply = self._synthesize_sub_agent_reply(
                profile, active_messages, assistant_record, target_model
            )
            if synth_reply:
                assistant_record += "\n\n" + synth_reply
                yield synth_reply
        return assistant_record

    def _persist_turn(
        self,
        handle: str,
        curr_session_id: str,
        history: list[dict[str, str]],
        h_key: str,
        user_message: str,
        assistant_record: str,
        complete_text: str,
    ) -> None:
        """Appends this turn to in-memory history and the on-disk session
        log, kicks off async session-title generation on the 3rd turn, and
        triggers background memory extraction."""
        with self._lock:
            history.extend(
                [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_record},
                ]
            )
            self.histories[h_key] = history[-(self.max_turns * 2) :]
        meta = SessionManager.append_turn(
            curr_session_id, handle, user_message, assistant_record
        )
        if meta and meta.get("turns_count") == 3:
            SessionManager.generate_smart_title_async(
                curr_session_id, handle, history[-6:], self.config
            )
        self.archivist.trigger_background_extraction(
            handle, user_message, complete_text
        )
