"""
Multi-Model Persona Execution Engine for Sympose.
"""

import os
import re
from typing import Dict, List, Any, Optional

from sympose.config import config_manager
import litellm

from sympose.profiles import ProfileManager
from sympose.memory import SessionArchivist
from sympose.commands import CommandInterceptor
from sympose.actions import ActionProcessor
from sympose.vault import VaultManager


class PersonaEngine:
    """Executes multi-model AI completions with sliding context, vault context injection, and autonomic actions."""

    def __init__(self, profile_manager: ProfileManager, max_turns: Optional[int] = None):
        self.pm = profile_manager
        self.config = config_manager
        self.archivist = SessionArchivist(profile_manager)
        self.max_turns = max_turns or int(self.config.get("performance.max_context_turns", 15))
        self.histories: Dict[str, List[Dict[str, str]]] = {}
        self.model_overrides: Dict[str, str] = {}

    def get_history(self, handle: str) -> List[Dict[str, str]]:
        return self.histories.setdefault(handle.lower(), [])

    def reset_history(self, handle: str) -> None:
        self.histories[handle.lower()] = []

    def summarize_session(self, handle: str, target: str = "both") -> Dict[str, Any]:
        return self.archivist.summarize_session(handle, self.get_history(handle), target=target)

    def _resolve_vault_context(self, profile: Dict[str, Any], message: str) -> Optional[str]:
        """Pre-fetches relevant vault notes or search matches if queried (<3ms local read)."""
        read_match = re.search(r"(?:read|open|check|look\s+at|show\s+me)\s+(?:the\s+)?note\s+([a-zA-Z0-9_\-/\.]+)", message, re.I)
        if read_match:
            note_name = read_match.group(1).strip()
            content = VaultManager.read_note(profile, note_name)
            return f"### Sandboxed Vault Note (`{note_name}`):\n{content}"

        search_match = re.search(r"(?:search|check|look\s+in|query)\s+(?:the\s+)?vault\s+(?:for\s+|about\s+)?(.+)", message, re.I)
        if search_match:
            query = search_match.group(1).strip()
            res = VaultManager.search(profile, query)
            return f"### Vault Search Results for '{query}':\n{res}"
        return None

    def spawn_sub_agent(self, target_handle: str, sub_prompt: str):
        target_profile = self.pm.get_profile(target_handle)
        if not target_profile:
            yield f"⚠️ Specialist agent `@{target_handle}` not found in profiles."
            return

        system_prompt = self.pm.build_system_prompt(target_profile)
        target_model = self.model_overrides.get(target_handle.lower(), target_profile.get("model", "gemini/gemini-3.5-flash-lite"))
        active_messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": sub_prompt}]

        if litellm is None:
            yield "⚠️ LiteLLM is not installed."
            return

        try:
            kwargs = {
                "model": target_model,
                "messages": active_messages,
                "stream": True,
                "timeout": float(self.config.get("performance.request_timeout", 10.0)),
            }
            if target_model.startswith("gemini/") and os.getenv("GEMINI_API_KEY"):
                kwargs["api_key"] = os.getenv("GEMINI_API_KEY")
            elif target_model.startswith("anthropic/") and os.getenv("ANTHROPIC_API_KEY"):
                kwargs["api_key"] = os.getenv("ANTHROPIC_API_KEY")
            elif target_model.startswith("openai/") and os.getenv("OPENAI_API_KEY"):
                kwargs["api_key"] = os.getenv("OPENAI_API_KEY")

            if "temperature" in target_profile:
                kwargs["temperature"] = target_profile["temperature"]
            if target_profile.get("api_base"):
                kwargs["api_base"] = target_profile["api_base"]

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

    def chat_stream(self, handle: str, user_message: str):
        profile = self.pm.get_profile(handle)
        if not profile:
            yield f"⚠️ Persona `@{handle}` not found."
            return

        clean_input = user_message.strip()
        cmd_gen = CommandInterceptor.intercept(self, handle, clean_input)
        if cmd_gen is not None:
            for item in cmd_gen:
                yield item
            return

        # Check Natural Language Memory intent
        nat_match = re.search(
            r"^(?:(?:hey|hi|hello)?\s*(?:@?\w+[,:]?\s*)?)?(?:please\s+)?remember\s+(?:that\s+|to\s+|:\s+)?(.+)$",
            clean_input, re.I
        )
        if nat_match and not clean_input.startswith("/"):
            extracted_fact = nat_match.group(1).strip()
            if extracted_fact:
                self.pm.append_memory(handle, extracted_fact)
                mem_file = profile.get("memory_file", f"profiles/{handle}_memory.md")
                yield f"> 🧠 **Persisted to {profile.get('name', handle)}'s memory (`{mem_file}`):**\n> *{extracted_fact}*\n\n"

        # Build dynamic composite prompt & inject pre-turn vault context if requested
        system_prompt = self.pm.build_system_prompt(profile)
        vault_ctx = self._resolve_vault_context(profile, clean_input)
        if vault_ctx:
            system_prompt += f"\n\n{vault_ctx}"

        history = self.get_history(handle)
        active_messages = [{"role": "system", "content": system_prompt}]
        active_messages.extend(history[-(self.max_turns * 2):])
        active_messages.append({"role": "user", "content": user_message})

        target_model = self.model_overrides.get(handle.lower(), profile.get("model", "gemini/gemini-3.5-flash-lite"))
        if litellm is None:
            yield "⚠️ LiteLLM is not installed. Run `pip install -r requirements.txt`."
            return

        try:
            kwargs = {
                "model": target_model,
                "messages": active_messages,
                "stream": bool(self.config.get("performance.stream", True)),
                "timeout": float(self.config.get("performance.request_timeout", 10.0)),
            }
            if target_model.startswith("gemini/") and os.getenv("GEMINI_API_KEY"):
                kwargs["api_key"] = os.getenv("GEMINI_API_KEY")
            elif target_model.startswith("anthropic/") and os.getenv("ANTHROPIC_API_KEY"):
                kwargs["api_key"] = os.getenv("ANTHROPIC_API_KEY")
            elif target_model.startswith("openai/") and os.getenv("OPENAI_API_KEY"):
                kwargs["api_key"] = os.getenv("OPENAI_API_KEY")

            if "temperature" in profile:
                kwargs["temperature"] = profile["temperature"]
            if profile.get("api_base"):
                kwargs["api_base"] = profile["api_base"]

            response = litellm.completion(**kwargs)
            full_reply = []
            for chunk in response:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full_reply.append(delta)
                    yield delta

            complete_text = "".join(full_reply)
            clean_text, badges = ActionProcessor.execute_actions(self.pm, handle, complete_text)
            has_worker = any("Sub-Agent Worker Report" in b for b in badges)

            if badges:
                badge_text = "\n\n" + "\n".join(badges)
                yield badge_text
                assistant_record = (clean_text + badge_text).strip()
            else:
                assistant_record = clean_text

            # Proactively trigger in-turn synthesis from primary agent if a worker executed
            if has_worker:
                yield "\n\n"
                synth_messages = list(active_messages)
                synth_messages.append({"role": "assistant", "content": assistant_record})
                synth_messages.append({
                    "role": "user",
                    "content": "[System Directive: Synthesize the worker report above. Present a crisp executive summary of findings, implications, and recommended next steps to the user.]"
                })

                synth_kwargs = dict(kwargs)
                synth_kwargs["messages"] = synth_messages
                try:
                    synth_resp = litellm.completion(**synth_kwargs)
                    synth_reply = []
                    for chunk in synth_resp:
                        delta = chunk.choices[0].delta.content or ""
                        if delta:
                            synth_reply.append(delta)
                            yield delta

                    final_synth = "".join(synth_reply).strip()
                    if final_synth:
                        assistant_record += "\n\n" + final_synth
                except Exception:
                    pass

            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": assistant_record})
            self.histories[handle.lower()] = history[-(self.max_turns * 2):]

            # Trigger non-blocking shadow extraction in background
            self.archivist.trigger_background_extraction(handle, user_message, complete_text)
        except Exception as e:
            err_str = str(e)
            if "11434" in err_str or "Connection refused" in err_str:
                yield f"⚠️ **Local Model Offline ({target_model}):** Run `ollama serve` to enable @{handle}."
            elif "API key" in err_str or "AuthenticationError" in err_str:
                yield f"⚠️ **Authentication Error:** Missing/invalid API key for `{target_model}`. Check `.env`."
            else:
                yield f"⚠️ **Runtime Error ({target_model}):** {err_str}"
