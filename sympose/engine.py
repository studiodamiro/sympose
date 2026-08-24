"""
Multi-Model Persona Execution Engine for Sympose.
"""

import os
from typing import Dict, List
import litellm

from sympose.profiles import ProfileManager
from sympose.vault import VaultManager


class PersonaEngine:
    """Executes multi-model AI completions with sliding context and command interceptors."""

    def __init__(self, profile_manager: ProfileManager, max_turns: int = 15):
        self.pm = profile_manager
        self.max_turns = max_turns
        self.histories: Dict[str, List[Dict[str, str]]] = {}
        self.model_overrides: Dict[str, str] = {}

    def get_history(self, handle: str) -> List[Dict[str, str]]:
        return self.histories.setdefault(handle.lower(), [])

    def reset_history(self, handle: str) -> None:
        self.histories[handle.lower()] = []

    def spawn_sub_agent(self, target_handle: str, sub_prompt: str):
        """Spawns an isolated single-turn sub-call to a specialist peer agent."""
        target_profile = self.pm.get_profile(target_handle)
        if not target_profile:
            yield f"⚠️ Specialist agent `@{target_handle}` not found in profiles."
            return

        system_prompt = self.pm.build_system_prompt(target_profile)
        target_model = self.model_overrides.get(target_handle.lower(), target_profile.get("model", "gemini/gemini-3.5-flash-lite"))
        api_base = target_profile.get("api_base")

        active_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": sub_prompt}
        ]

        if litellm is None:
            yield "⚠️ LiteLLM is not installed."
            return

        try:
            kwargs = {
                "model": target_model,
                "messages": active_messages,
                "stream": True,
            }
            if target_model.startswith("gemini/") and os.getenv("GEMINI_API_KEY"):
                kwargs["api_key"] = os.getenv("GEMINI_API_KEY")
            elif target_model.startswith("anthropic/") and os.getenv("ANTHROPIC_API_KEY"):
                kwargs["api_key"] = os.getenv("ANTHROPIC_API_KEY")
            elif target_model.startswith("openai/") and os.getenv("OPENAI_API_KEY"):
                kwargs["api_key"] = os.getenv("OPENAI_API_KEY")

            if "temperature" in target_profile:
                kwargs["temperature"] = target_profile["temperature"]
            if api_base:
                kwargs["api_base"] = api_base

            response = litellm.completion(**kwargs)
            for chunk in response:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    yield delta
        except Exception as e:
            err_str = str(e)
            if "11434" in err_str or "Connection refused" in err_str:
                yield f"⚠️ **Local Model Offline ({target_model}):** Run `ollama serve` to enable @{target_handle}."
            else:
                yield f"⚠️ Delegation error ({target_model}): {err_str}"

    def chat_stream(self, handle: str, user_message: str):
        """Streams AI responses token-by-token or yields instant command replies."""
        profile = self.pm.get_profile(handle)
        if not profile:
            yield f"⚠️ Persona `@{handle}` not found."
            return

        clean_input = user_message.strip()

        # Intercept tactical slash commands
        if clean_input in ("/reset", "/new"):
            self.reset_history(handle)
            yield f"Reset conversation history for {profile.get('name', handle)}. Context refreshed."
            return

        if clean_input.startswith("/remember "):
            fact = clean_input[10:].strip()
            if not fact:
                yield "Usage: `/remember <fact to save>`"
                return
            success = self.pm.append_memory(handle, fact)
            if success:
                yield f"Saved to {profile.get('name', handle)}'s memory:\n> {fact}"
            else:
                yield f"Error: Failed to save memory to {profile.get('name', handle)}."
            return

        if clean_input.startswith("/model "):
            new_model = clean_input[7:].strip()
            if not new_model:
                yield "Usage: `/model <provider/model_name>`"
                return
            self.model_overrides[handle.lower()] = new_model
            yield f"Model for {profile.get('name', handle)} temporarily set to `{new_model}` for this session."
            return

        if clean_input.startswith("/vault "):
            query = clean_input[7:].strip()
            if not query:
                yield "Usage: `/vault <search query>`"
                return
            yield VaultManager.search(profile, query)
            return

        if clean_input.startswith("/note "):
            parts = clean_input[6:].strip().split(maxsplit=1)
            if len(parts) < 2:
                yield "Usage: `/note <filename.md> <content to write>`"
                return
            yield VaultManager.write_note(profile, parts[0], parts[1])
            return

        if clean_input.startswith("/daily "):
            reflection = clean_input[7:].strip()
            if not reflection:
                yield "Usage: `/daily <your reflection>`"
                return
            yield VaultManager.write_daily_note(profile, reflection)
            return

        if clean_input.startswith("/ask "):
            parts = clean_input[5:].strip().split(maxsplit=1)
            if len(parts) < 2:
                yield "Usage: `/ask <@persona> <task or question>`"
                return
            target = parts[0].replace("@", "").lower()
            sub_prompt = parts[1]
            target_profile = self.pm.get_profile(target)
            if not target_profile:
                yield f"Specialist agent `@{target}` not found."
                return

            yield f"[Delegating to {target_profile.get('name', target)} ({target_profile.get('title', 'Specialist')}):]\n\n"
            for chunk in self.spawn_sub_agent(target, sub_prompt):
                yield chunk
            return

        if clean_input == "/help":
            yield (
                "**Available Slash Commands:**\n"
                "- `/ask <@persona> <task>`: Delegate an isolated sub-task to a peer\n"
                "- `/note <file.md> <content>`: Create or append to a sandboxed vault note\n"
                "- `/daily <reflection>`: Append to Daily Notes/YYYY-MM-DD.md\n"
                "- `/remember <fact>`: Save fact into persona's persistent `_memory.md`\n"
                "- `/reset` or `/new`: Clear active conversation context\n"
                "- `/model <name>`: Temporarily switch backend model\n"
                "- `/vault <query>`: Query persona's sandboxed notes\n"
                "- `/help`: Show this command list"
            )
            return

        # Build dynamic system prompt
        system_prompt = self.pm.build_system_prompt(profile)
        history = self.get_history(handle)

        active_messages = [{"role": "system", "content": system_prompt}]
        active_messages.extend(history[-(self.max_turns * 2):])
        active_messages.append({"role": "user", "content": user_message})

        target_model = self.model_overrides.get(handle.lower(), profile.get("model", "gemini/gemini-3.5-flash-lite"))
        api_base = profile.get("api_base")

        if litellm is None:
            yield "⚠️ LiteLLM is not installed. Please run `pip install -r requirements.txt`."
            return

        try:
            kwargs = {
                "model": target_model,
                "messages": active_messages,
                "stream": True,
                "timeout": 10.0,
            }
            if target_model.startswith("gemini/") and os.getenv("GEMINI_API_KEY"):
                kwargs["api_key"] = os.getenv("GEMINI_API_KEY")
            elif target_model.startswith("anthropic/") and os.getenv("ANTHROPIC_API_KEY"):
                kwargs["api_key"] = os.getenv("ANTHROPIC_API_KEY")
            elif target_model.startswith("openai/") and os.getenv("OPENAI_API_KEY"):
                kwargs["api_key"] = os.getenv("OPENAI_API_KEY")

            if "temperature" in profile:
                kwargs["temperature"] = profile["temperature"]
            if api_base:
                kwargs["api_base"] = api_base

            response = litellm.completion(**kwargs)
            full_reply = []

            for chunk in response:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full_reply.append(delta)
                    yield delta

            complete_text = "".join(full_reply)
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": complete_text})
            self.histories[handle.lower()] = history[-(self.max_turns * 2):]

        except Exception as e:
            err_str = str(e)
            if "11434" in err_str or "Connection refused" in err_str:
                yield (
                    f"⚠️ **Local Model Offline ({target_model})**\n\n"
                    f"Marcus Aurelius runs locally on your Mac. Please start the Ollama daemon by running:\n"
                    f"```bash\nollama serve\n```"
                )
            elif "API key" in err_str or "AuthenticationError" in err_str:
                yield f"⚠️ **Authentication Error:** Missing or invalid API key for model `{target_model}`. Check `.env`."
            else:
                yield f"⚠️ **Runtime Error ({target_model}):** {err_str}"
