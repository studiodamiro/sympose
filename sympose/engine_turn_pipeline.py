"""
PersonaEngine's per-turn chat pipeline — everything from parsing a raw
user message through streaming, grounding enforcement, sub-agent
synthesis, and session persistence. This is the ADR-124 `chat_stream`
decomposition, split into its own module per ADR-125 purely to keep
engine.py under this project's own size guidance.

`chat_stream` itself is the only method still defined here: the rest of
this original cluster is now spread across `engine_turn_setup.py`
(pre-model turn prep), `engine_turn_grounding.py` (calling the model and
enforcing ADR-124 grounding), and `engine_turn_finalize.py` (trimming the
reply, sub-agent synthesis, persistence) — a second-pass split per
ADR-125's own note that this cluster would need one once it was out of
engine.py and easier to judge. `TurnPipelineMixin` composes all three, so
`engine.py`'s own `class PersonaEngine(..., TurnPipelineMixin)` doesn't
need to change; every method is unchanged from its prior home.

These methods share ~10 pieces of `PersonaEngine` instance state
(`self.pm`, `self._lock`, `self.active_vault_ctx`, `self.active_ritual`,
`self.config`, `self.histories`, `self.archivist`, plus several sibling
methods from `GroundingHelpersMixin` and `PersonaEngine` itself). A mixin
keeps all of that resolving normally through the MRO once `PersonaEngine`
inherits from this class, rather than threading it through explicit
function parameters.
"""

from collections.abc import Callable

import litellm

from sympose.commands import CommandInterceptor
from sympose.config import DEFAULT_CHAT_MODEL
from sympose.engine_turn_finalize import TurnFinalizeMixin
from sympose.engine_turn_grounding import TurnGroundingMixin
from sympose.engine_turn_setup import TurnSetupMixin


class TurnPipelineMixin(TurnSetupMixin, TurnGroundingMixin, TurnFinalizeMixin):
    def chat_stream(
        self,
        handle: str,
        user_message: str,
        session_id: str | None = None,
        on_sub_agent_progress: Callable[[str], None] | None = None,
    ):
        profile = self.pm.get_profile(handle)
        if not profile:
            yield f"⚠️ Persona `@{handle}` not found."
            return

        clean_input = user_message.strip()
        cmd_gen = CommandInterceptor.intercept(self, handle, clean_input)
        if cmd_gen is not None:
            yield from cmd_gen
            return

        persisted_msg = self._maybe_persist_remembered_fact(
            handle, profile, clean_input
        )
        if persisted_msg:
            yield persisted_msg

        # Build dynamic composite prompt & inject active turn vault context via VaultManager
        curr_session_id = session_id or self.get_active_session_id(handle)
        vault_ctx, h_key = self._resolve_turn_vault_context(
            handle, session_id, profile, clean_input
        )
        system_prompt, vault_ctx = self._build_turn_system_prompt(
            handle, profile, vault_ctx, h_key, clean_input, curr_session_id
        )

        history = self.get_history(handle, session_id=session_id)
        active_messages = [{"role": "system", "content": system_prompt}]
        active_messages.extend(history[-(self.max_turns * 2) :])
        active_messages.append({"role": "user", "content": user_message})

        target_model = (
            self.get_model_override(handle)
            or profile.get("model")
            or DEFAULT_CHAT_MODEL
        )
        if litellm is None:
            yield "⚠️ LiteLLM is not installed. Run `pip install -r requirements.txt`."
            return

        call_model, routed_local = self._select_turn_model(
            handle, profile, clean_input, vault_ctx, target_model
        )

        grounding_mode = self._grounding_mode(profile, call_model)
        is_full_body_ctx = self._is_full_body_vault_ctx(vault_ctx)
        strict = grounding_mode == "strict" and not is_full_body_ctx
        # A real note body being present doesn't guarantee the model actually
        # relayed it faithfully - hold the stream here too so a mismatched
        # citation can be caught and swapped for the real thing before the
        # user ever sees the invented one.
        verify_ctx = grounding_mode == "strict" and is_full_body_ctx
        hold_stream = strict or verify_ctx

        try:
            stream_val = bool(self.config.get("performance.stream"))
            held: list[str] = []
            complete_text = yield from self._call_and_stream_model(
                call_model,
                routed_local,
                profile,
                active_messages,
                target_model,
                stream_val,
                hold_stream,
                held,
            )

            clean_text, badges, has_sub_agent, has_retrieval, was_forced = (
                yield from self._apply_grounding_and_stream_result(
                    handle,
                    profile,
                    clean_input,
                    complete_text,
                    vault_ctx,
                    strict,
                    verify_ctx,
                    hold_stream,
                    held,
                    history,
                    on_sub_agent_progress,
                )
            )

            clean_text, assistant_record = self._finalize_reply_text(
                complete_text, clean_text, badges, has_retrieval, was_forced
            )

            # Always synthesise a grounded final answer from the sub-agent report:
            # the model's pre-tag text was trimmed as a guess above, and the
            # report now carries the verbatim note text for it to quote.
            assistant_record = yield from self._emit_badges_and_synthesis(
                profile,
                active_messages,
                badges,
                assistant_record,
                has_sub_agent,
                target_model,
            )

            self._persist_turn(
                handle,
                curr_session_id,
                history,
                h_key,
                user_message,
                assistant_record,
                complete_text,
            )
        except Exception as e:
            err = str(e)
            yield (
                f"⚠️ **Local Model Offline ({target_model}):** Run `ollama serve`."
                if ("11434" in err or "Connection refused" in err)
                else f"⚠️ **Runtime Error ({target_model}):** {err}"
            )
