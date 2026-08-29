"""
Multi-Model Persona Execution Engine for Sympose.
"""

import os, re
from typing import Dict, List, Any, Optional
import litellm

from sympose.config import config_manager
from sympose.profiles import ProfileManager
from sympose.memory import SessionArchivist
from sympose.commands import CommandInterceptor
from sympose.actions import ActionProcessor
from sympose.vault import VaultManager
from sympose.sessions import SessionManager


class PersonaEngine:
    """Executes multi-model AI completions with sliding context, vault context injection, and autonomic actions."""

    def __init__(self, profile_manager: ProfileManager, max_turns: Optional[int] = None):
        self.pm, self.config, self.archivist = profile_manager, config_manager, SessionArchivist(profile_manager)
        self.max_turns = max_turns or int(self.config.get("performance.max_context_turns", 15))
        self.histories: Dict[str, List[Dict[str, str]]] = {}
        self.active_sessions: Dict[str, str] = {}
        self.model_overrides: Dict[str, str] = {}
        self.active_vault_ctx: Dict[str, str] = {}

    def _get_history_key(self, handle: str, session_id: Optional[str] = None) -> str:
        return f"{handle.lower()}::{session_id}" if session_id else handle.lower()

    def get_history(self, handle: str, session_id: Optional[str] = None) -> List[Dict[str, str]]:
        return self.histories.setdefault(self._get_history_key(handle, session_id), [])

    def get_active_session_id(self, handle: str) -> str:
        h_low = handle.lower()
        if h_low not in self.active_sessions:
            meta = SessionManager.create_session(h_low)
            self.active_sessions[h_low] = meta["session_id"]
        return self.active_sessions[h_low]

    def new_session(self, handle: str) -> str:
        h_low = handle.lower()
        self.reset_history(h_low)
        meta = SessionManager.create_session(h_low)
        self.active_sessions[h_low] = meta["session_id"]
        return meta["session_id"]

    def resume_session(self, handle: str, session_id: str) -> Optional[Dict[str, Any]]:
        h_low = handle.lower()
        session = SessionManager.load_session(session_id)
        if not session:
            return None
        self.active_sessions[h_low] = session_id
        k_turns = int(self.config.get("performance.resume_context_turns", 6))
        turns = session.get("turns", [])
        recent_turns = turns[-k_turns:] if k_turns > 0 else turns
        hydrated: List[Dict[str, str]] = []
        for t in recent_turns:
            if t.get("user"):
                hydrated.append({"role": "user", "content": t["user"]})
            if t.get("assistant"):
                hydrated.append({"role": "assistant", "content": t["assistant"]})
        h_key = self._get_history_key(h_low)
        self.histories[h_key] = hydrated
        return session

    def reset_history(self, handle: str, session_id: Optional[str] = None) -> None:
        if session_id:
            k = self._get_history_key(handle, session_id)
            self.histories[k] = []
            self.active_vault_ctx.pop(k, None)
        else:
            h_low = handle.lower()
            prefix = f"{h_low}::"
            self.histories[h_low] = []
            self.active_vault_ctx.pop(h_low, None)
            self.active_sessions.pop(h_low, None)
            for k in list(self.histories.keys()):
                if k.startswith(prefix):
                    self.histories.pop(k, None)
            for k in list(self.active_vault_ctx.keys()):
                if k.startswith(prefix):
                    self.active_vault_ctx.pop(k, None)

    def summarize_session(self, handle: str, target: str = "both", session_id: Optional[str] = None) -> Dict[str, Any]:
        curr_session_id = session_id or self.active_sessions.get(handle.lower())
        res = self.archivist.summarize_session(handle, self.get_history(handle, session_id=session_id), target=target)
        if res.get("status") == "success" and curr_session_id:
            obs_text = res.get("obsidian_content", "")
            if obs_text:
                first_h = re.search(r"^(?:#|##)\s*(?:Session:?\s*)?([^\n]+)", obs_text, re.M)
                if first_h and first_h.group(1).strip():
                    SessionManager.update_session_title(curr_session_id, first_h.group(1).strip())
        return res

    def _build_kwargs(self, target_model: str, profile: Dict[str, Any], messages: List[Dict[str, Any]], stream: bool = True) -> Dict[str, Any]:
        is_loc = target_model.startswith("ollama/") or ":11434" in str(profile.get("api_base", ""))
        to_key = "performance.local_request_timeout" if is_loc else "performance.request_timeout"
        kwargs = {"model": target_model, "messages": messages, "stream": stream, "timeout": float(self.config.get(to_key, 60.0 if is_loc else 10.0))}
        for pfx, key in (("gemini/", "GEMINI_API_KEY"), ("anthropic/", "ANTHROPIC_API_KEY"), ("openai/", "OPENAI_API_KEY"), ("openrouter/", "OPENROUTER_API_KEY")):
            if target_model.startswith(pfx) and os.getenv(key):
                kwargs["api_key"] = os.getenv(key)
        if "temperature" in profile: kwargs["temperature"] = profile["temperature"]
        if profile.get("api_base"): kwargs["api_base"] = profile["api_base"]
        return kwargs

    def spawn_sub_agent(self, target_handle: str, sub_prompt: str):
        target_profile = self.pm.get_profile(target_handle)
        if not target_profile:
            yield f"⚠️ Specialist agent `@{target_handle}` not found in profiles."
            return

        system_prompt = self.pm.build_system_prompt(target_profile)
        target_model = self.model_overrides.get(target_handle.lower(), target_profile.get("model") or os.getenv("DEFAULT_MODEL", "gemini/gemini-3.6-flash"))
        active_messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": sub_prompt}]
        if litellm is None:
            yield "⚠️ LiteLLM is not installed."
            return

        try:
            kwargs = self._build_kwargs(target_model, target_profile, active_messages, stream=True)
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

    def chat_stream(self, handle: str, user_message: str, session_id: Optional[str] = None):
        profile = self.pm.get_profile(handle)
        if not profile:
            yield f"⚠️ Persona `@{handle}` not found."
            return

        clean_input = user_message.strip()
        cmd_gen = CommandInterceptor.intercept(self, handle, clean_input)
        if cmd_gen is not None:
            for item in cmd_gen: yield item
            return

        nat_match = re.search(r"^(?:(?:hey|hi|hello)?\s*(?:@?\w+[,:]?\s*)?)?(?:please\s+)?remember\s+(?:that\s+|to\s+|:\s+)?(.+)$", clean_input, re.I)
        if nat_match and not clean_input.startswith("/"):
            extracted_fact = nat_match.group(1).strip()
            if extracted_fact:
                self.pm.append_memory(handle, extracted_fact)
                yield f"> 🧠 **Persisted to {profile.get('name', handle)}'s memory:** *{extracted_fact}*\n\n"

        # Build dynamic composite prompt & inject active turn vault context via VaultManager
        curr_session_id = session_id or self.get_active_session_id(handle)
        h_key = self._get_history_key(handle, session_id)
        vault_ctx = VaultManager.resolve_turn_context(profile, clean_input)
        if vault_ctx:
            self.active_vault_ctx[h_key] = vault_ctx
        elif h_key in self.active_vault_ctx and self.active_vault_ctx[h_key]:
            vault_ctx = self.active_vault_ctx[h_key]

        system_prompt = self.pm.build_system_prompt(profile)
        if vault_ctx:
            system_prompt += f"\n\n{vault_ctx}"

        history = self.get_history(handle, session_id=session_id)
        active_messages = [{"role": "system", "content": system_prompt}]
        active_messages.extend(history[-(self.max_turns * 2):])
        active_messages.append({"role": "user", "content": user_message})

        target_model = self.model_overrides.get(handle.lower(), profile.get("model") or os.getenv("DEFAULT_MODEL", "gemini/gemini-3.6-flash"))
        if litellm is None:
            yield "⚠️ LiteLLM is not installed. Run `pip install -r requirements.txt`."
            return

        try:
            stream_val = bool(self.config.get("performance.stream", True))
            response = litellm.completion(**self._build_kwargs(target_model, profile, active_messages, stream=stream_val))
            full_reply = []
            for chunk in response:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full_reply.append(delta)
                    yield delta

            complete_text = "".join(full_reply)
            clean_text, badges = ActionProcessor.execute_actions(self.pm, handle, complete_text, user_prompt=clean_input)
            has_worker = any("Sub-Agent Worker Report" in b or "Live Web Search Report" in b for b in badges)
            assistant_record = (clean_text + ("\n\n" + "\n".join(badges) if badges else "")).strip()
            if badges:
                yield "\n\n" + "\n".join(badges)

            if has_worker:
                yield "\n\n"
                synth_msgs = list(active_messages) + [{"role": "assistant", "content": assistant_record}, {"role": "user", "content": "[System Directive: Synthesize the live data / report above to provide the direct calculation and final answer to the user.]"}]
                try:
                    synth_resp = litellm.completion(**self._build_kwargs(target_model, profile, synth_msgs, stream=True))
                    synth_reply = "".join([c.choices[0].delta.content or "" for c in synth_resp if c.choices[0].delta.content]).strip()
                    if synth_reply:
                        assistant_record += "\n\n" + synth_reply
                        yield synth_reply
                except Exception:
                    pass

            history.extend([{"role": "user", "content": user_message}, {"role": "assistant", "content": assistant_record}])
            h_key = self._get_history_key(handle, session_id)
            self.histories[h_key] = history[-(self.max_turns * 2):]
            meta = SessionManager.append_turn(curr_session_id, handle, user_message, assistant_record)
            if meta and meta.get("turns_count") == 3:
                SessionManager.generate_smart_title_async(curr_session_id, handle, history[-6:], self.config)
            self.archivist.trigger_background_extraction(handle, user_message, complete_text)
        except Exception as e:
            err = str(e)
            yield f"⚠️ **Local Model Offline ({target_model}):** Run `ollama serve`." if ("11434" in err or "Connection refused" in err) else f"⚠️ **Runtime Error ({target_model}):** {err}"
