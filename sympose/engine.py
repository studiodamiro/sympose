"""
Multi-Model Persona Execution Engine for Sympose.
"""

import logging
import re
import threading
from typing import Any

import litellm

log = logging.getLogger(__name__)

from sympose.config import DEFAULT_CHAT_MODEL, config_manager, is_local_backend
from sympose.engine_grounding import GroundingHelpersMixin
from sympose.engine_turn_pipeline import TurnPipelineMixin
from sympose.memory import SessionArchivist
from sympose.model_router import resolve_turn_model, resolve_turn_model_by_capability
from sympose.models import resolve_api_key
from sympose.profiles import ProfileManager
from sympose.sessions import SessionManager
from sympose.vault import VaultManager


class PersonaEngine(GroundingHelpersMixin, TurnPipelineMixin):
    """Executes multi-model AI completions with sliding context, vault context injection, and autonomic actions."""

    def __init__(self, profile_manager: ProfileManager, max_turns: int | None = None):
        self.pm, self.config, self.archivist = (
            profile_manager,
            config_manager,
            SessionArchivist(profile_manager),
        )
        self.max_turns = max_turns or int(
            self.config.get("performance.max_context_turns")
        )
        self.histories: dict[str, list[dict[str, str]]] = {}
        self.active_sessions: dict[str, str] = {}
        self.model_overrides: dict[str, str] = {}
        self.active_vault_ctx: dict[str, str] = {}
        # True once a "pull a random note" ritual (ADR: see
        # resolve_ritual_random_pull's docstring) has actually fetched a real
        # note this session, so a later continuation turn ("let's do another
        # one") that repeats none of the memory fact's own wording can still
        # keep pulling real notes instead of freewheeling once the phrase
        # that first triggered it stops being repeated.
        self.active_ritual: dict[str, bool] = {}
        # Guards mutation of the four dicts above. One PersonaEngine is shared
        # across every Slack daemon thread (one per concurrent in-flight
        # message), so check-then-act sequences on this state need to be atomic.
        self._lock = threading.RLock()

    def _get_history_key(self, handle: str, session_id: str | None = None) -> str:
        return f"{handle.lower()}::{session_id}" if session_id else handle.lower()

    def get_history(
        self, handle: str, session_id: str | None = None
    ) -> list[dict[str, str]]:
        with self._lock:
            return self.histories.setdefault(
                self._get_history_key(handle, session_id), []
            )

    def get_active_session_id(self, handle: str) -> str:
        h_low = handle.lower()
        with self._lock:
            if h_low not in self.active_sessions:
                meta = SessionManager.create_session(h_low)
                self.active_sessions[h_low] = meta["session_id"]
            return self.active_sessions[h_low]

    def new_session(self, handle: str) -> str:
        h_low = handle.lower()
        self.reset_history(h_low)
        meta = SessionManager.create_session(h_low)
        with self._lock:
            self.active_sessions[h_low] = meta["session_id"]
        return meta["session_id"]

    def resume_session(self, handle: str, session_id: str) -> dict[str, Any] | None:
        h_low = handle.lower()
        session = SessionManager.load_session(session_id)
        if not session:
            return None
        k_turns = int(self.config.get("performance.resume_context_turns"))
        turns = session.get("turns", [])
        recent_turns = turns[-k_turns:] if k_turns > 0 else turns
        hydrated: list[dict[str, str]] = []
        for t in recent_turns:
            if t.get("user"):
                hydrated.append({"role": "user", "content": t["user"]})
            if t.get("assistant"):
                hydrated.append({"role": "assistant", "content": t["assistant"]})
        h_key = self._get_history_key(h_low)
        with self._lock:
            self.active_sessions[h_low] = session_id
            self.histories[h_key] = hydrated
        return session

    def reset_history(self, handle: str, session_id: str | None = None) -> None:
        with self._lock:
            if session_id:
                k = self._get_history_key(handle, session_id)
                self.histories[k] = []
                self.active_vault_ctx.pop(k, None)
                self.active_ritual.pop(k, None)
            else:
                h_low = handle.lower()
                prefix = f"{h_low}::"
                self.histories[h_low] = []
                self.active_vault_ctx.pop(h_low, None)
                self.active_ritual.pop(h_low, None)
                self.active_sessions.pop(h_low, None)
                for k in list(self.histories.keys()):
                    if k.startswith(prefix):
                        self.histories.pop(k, None)
                for k in list(self.active_vault_ctx.keys()):
                    if k.startswith(prefix):
                        self.active_vault_ctx.pop(k, None)
                for k in list(self.active_ritual.keys()):
                    if k.startswith(prefix):
                        self.active_ritual.pop(k, None)

    def get_model_override(self, handle: str) -> str | None:
        with self._lock:
            return self.model_overrides.get(handle.lower())

    def set_model_override(self, handle: str, model: str) -> None:
        with self._lock:
            self.model_overrides[handle.lower()] = model

    def clear_model_override(self, handle: str) -> str | None:
        with self._lock:
            return self.model_overrides.pop(handle.lower(), None)

    def summarize_session(
        self, handle: str, target: str = "both", session_id: str | None = None
    ) -> dict[str, Any]:
        curr_session_id = session_id or self.active_sessions.get(handle.lower())
        res = self.archivist.summarize_session(
            handle, self.get_history(handle, session_id=session_id), target=target
        )
        if res.get("status") == "success" and curr_session_id:
            obs_text = res.get("obsidian_content", "")
            if obs_text:
                first_h = re.search(
                    r"^(?:#|##)\s*(?:Session:?\s*)?([^\n]+)", obs_text, re.MULTILINE
                )
                if first_h and first_h.group(1).strip():
                    SessionManager.update_session_title(
                        curr_session_id, first_h.group(1).strip()
                    )
        return res

    def _resolve_keep_alive(
        self, profile: dict[str, Any], model: str
    ) -> str | int | None:
        """Ollama residency for `model`. keep_alive is a property of which
        model is loaded into Ollama, not which persona is calling it — two
        personas pointed at the same model string but different keep_alive
        values would otherwise just overwrite each other's residency on
        every call. So `performance.local_model_keep_alive[model]` (keyed by
        exact model id) is the one source of truth once that happens; a
        persona's own `keep_alive` covers the common single-persona case
        without needing an entry in that map; `performance.local_keep_alive`
        is the blanket fallback; None leaves it to the server-wide
        OLLAMA_KEEP_ALIVE env var. Accepts -1 (forever), 0 (unload now), or
        a duration string like "30m"."""
        per_model = self.config.get("performance.local_model_keep_alive") or {}
        if model in per_model:
            return per_model[model]
        ka = profile.get("keep_alive")
        if ka is not None:
            return ka
        return self.config.get("performance.local_keep_alive")

    def _build_kwargs(
        self,
        target_model: str,
        profile: dict[str, Any],
        messages: list[dict[str, Any]],
        stream: bool = True,
    ) -> dict[str, Any]:
        is_loc = is_local_backend(target_model, profile.get("api_base", ""))
        to_key = (
            "performance.local_request_timeout"
            if is_loc
            else "performance.request_timeout"
        )
        kwargs = {
            "model": target_model,
            "messages": messages,
            "stream": stream,
            "timeout": float(self.config.get(to_key)),
        }
        api_key = resolve_api_key(target_model)
        if api_key:
            kwargs["api_key"] = api_key
        if "temperature" in profile:
            kwargs["temperature"] = profile["temperature"]
        if profile.get("api_base"):
            kwargs["api_base"] = profile["api_base"]
        if is_loc:
            ka = self._resolve_keep_alive(profile, target_model)
            if ka is not None:
                kwargs["keep_alive"] = ka
            kwargs["stop"] = list(self._LOCAL_RUNAWAY_STOP_SEQUENCES)
        return kwargs

    def _select_turn_model(
        self,
        handle: str,
        profile: dict[str, Any],
        clean_input: str,
        vault_ctx: str | None,
        target_model: str,
    ) -> tuple[str, bool]:
        """ADR-122: decides whether this turn routes to the persona's own
        cheap `local_model` instead of `target_model`. Returns
        (model_to_use, routed_local) — never blocks on a cold local model
        (see model_router.resolve_turn_model).

        Skipped entirely (stays on target_model) when: no local_model is
        configured for this persona; the user has a manual /model override
        active — that's an explicit choice this shouldn't second-guess; or
        this turn already resolved (or clearly wants) vault content — a
        small local model summarizing retrieved notes is exactly the case
        strict grounding exists to guard against.

        A persona with `capability_min_tier` set (ADR-135) replaces the
        SIMPLE-message gate below with capability-tier resolution instead —
        every message reaching this point (the exclusions above still
        apply) routes to local_model whenever its declared tier clears that
        floor, regardless of message length/complexity. Empty (default):
        today's SIMPLE-message-only behavior, byte-for-byte unchanged."""
        local_model = str(profile.get("local_model") or "").strip()
        if (
            not local_model
            or self.get_model_override(handle)
            or vault_ctx
            or VaultManager.has_recall_intent(clean_input)
        ):
            return target_model, False
        keep_alive = self._resolve_keep_alive(profile, local_model)
        min_tier = str(profile.get("capability_min_tier") or "").strip()
        if min_tier:
            return resolve_turn_model_by_capability(
                target_model,
                local_model,
                self.config.get("models.capability_tier_order"),
                self.config.get("models.capability_tiers"),
                min_tier,
                keep_alive=keep_alive,
            )
        return resolve_turn_model(
            target_model, local_model, clean_input, keep_alive=keep_alive
        )

    def consult_persona(self, target_handle: str, sub_prompt: str):
        target_profile = self.pm.get_profile(target_handle)
        if not target_profile:
            yield f"⚠️ Specialist persona `@{target_handle}` not found in profiles."
            return

        system_prompt = self.pm.build_system_prompt(target_profile)
        target_model = (
            self.get_model_override(target_handle)
            or target_profile.get("model")
            or DEFAULT_CHAT_MODEL
        )
        active_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": sub_prompt},
        ]
        if litellm is None:
            yield "⚠️ LiteLLM is not installed."
            return

        try:
            kwargs = self._build_kwargs(
                target_model, target_profile, active_messages, stream=True
            )
            response = litellm.completion(**kwargs)
            for chunk in response:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    yield delta
        except Exception as e:
            err_str = str(e)
            yield (
                f"⚠️ **Local Model Offline ({target_model}):** Run `ollama serve` to enable @{target_handle}."
                if ("11434" in err_str or "Connection refused" in err_str)
                else f"⚠️ Delegation error ({target_model}): {err_str}"
            )

    def _visible_stream(self, response: Any, sink: list[str]):
        """Yield model text for display, but stop the moment any autonomic
        action tag begins (`[SEARCH …]`, `[WRITE_NOTE …]`, `[REMEMBER …]`, ...):
        for a retrieval tag the runtime will inject the real report, so a weak
        local model that keeps 'reading out' the note it has not seen yet
        must not reach the user; for every other tag, its bracket syntax is
        internal wire format that was never meant to be user-visible in the
        first place. The full raw text still lands in `sink[0]` for
        `ActionProcessor`. A short hold-back keeps a tag that is split across
        chunks from leaking its first characters."""
        HOLDBACK = 24
        buf: list[str] = []
        emitted = 0
        gate_open = True
        for chunk in response:
            try:
                delta = chunk.choices[0].delta.content or ""
            except (AttributeError, IndexError):
                delta = ""
            if not delta:
                continue
            buf.append(delta)
            if not gate_open:
                continue
            text = "".join(buf)
            m = self._ANY_ACTION_TAG_RE.search(text)
            if m:
                if m.start() > emitted:
                    yield text[emitted : m.start()]
                emitted = m.start()
                gate_open = False
                continue
            safe = len(text) - HOLDBACK
            if safe > emitted:
                yield text[emitted:safe]
                emitted = safe
        full = "".join(buf)
        if gate_open and len(full) > emitted:
            yield full[emitted:]
        sink.append(full)
