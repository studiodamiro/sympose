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


class PersonaEngine:
    """Executes multi-model AI completions with sliding context, vault context injection, and autonomic actions."""

    def __init__(self, profile_manager: ProfileManager, max_turns: Optional[int] = None):
        self.pm, self.config, self.archivist = profile_manager, config_manager, SessionArchivist(profile_manager)
        self.max_turns = max_turns or int(self.config.get("performance.max_context_turns", 15))
        self.histories: Dict[str, List[Dict[str, str]]] = {}
        self.model_overrides: Dict[str, str] = {}
        self.active_vault_ctx: Dict[str, str] = {}

    def get_history(self, handle: str) -> List[Dict[str, str]]:
        return self.histories.setdefault(handle.lower(), [])

    def reset_history(self, handle: str) -> None:
        self.histories[handle.lower()] = []
        self.active_vault_ctx.pop(handle.lower(), None)

    def summarize_session(self, handle: str, target: str = "both") -> Dict[str, Any]:
        return self.archivist.summarize_session(handle, self.get_history(handle), target=target)

    def _resolve_vault_context(self, profile: Dict[str, Any], message: str) -> Optional[str]:
        msg = message.strip()
        # Direct note title lookup across allowed folders (e.g. Miro, Summit, Virginia)
        for w in re.findall(r"[a-zA-Z0-9_\-]+", msg):
            if len(w) >= 3 and w.lower() not in {"the", "and", "for", "with", "this", "that", "from", "when", "what", "where", "your", "have", "sure", "look", "tell", "about", "some", "here", "will", "does"}:
                content = VaultManager.read_note(profile, w)
                if content and not content.startswith("Note `") and not content.startswith("⚠️"):
                    return f"### Sandboxed Vault Note (`{w}`):\n{content}"

        rd = re.search(r"(?:read|open|check|look\s+at|show\s+me)\s+(?:the\s+)?note\s+([a-zA-Z0-9_\-/\.\s]+(?:\.md|\.markdown|\.txt|[a-zA-Z0-9]))", msg, re.I)
        if rd:
            return f"### Sandboxed Vault Note (`{rd.group(1).strip()}`):\n{VaultManager.read_note(profile, rd.group(1).strip())}"

        yr = re.search(r"\b(201\d|202\d|19\d\d)\b", msg)
        if yr and re.search(r"(?:vault|journal|note|notes|daily|reflection|reminisce|entry|entries|wayback|past)", msg, re.I):
            return f"### Vault Search Results for '{yr.group(1)}':\n{VaultManager.search(profile, yr.group(1))}"

        # Dynamic domain scanning derived from agent's configured vault_folders & config.yaml triggers
        v_folders = profile.get("vault_folders") or [profile.get("vault_folder", "General")]
        triggers = self.config.get("vault.search_triggers") or ["vault", "note", "notes", "folder", "search", "find", "who", "what", "access"]
        has_intent = any(k in msg.lower() for k in triggers)

        for folder in v_folders:
            if not folder or folder in ("*", "", "all"):
                continue
            f_clean = folder.strip().lower()
            variants = {f_clean, f_clean[:-1] if f_clean.endswith("s") else f_clean + "s"}
            if f_clean == "people":
                variants.update({"person", "contact", "contacts", "friend", "friends", "family"})
            elif f_clean == "movies":
                variants.update({"film", "films", "cinema"})

            if any(re.search(rf"\b{re.escape(v)}\b", msg, re.I) for v in variants) and has_intent:
                if re.search(r"\b(scan|analyze|summarize|all|overview|entries|how\s+i|about\s+me|amuse|connections?)\b", msg, re.I):
                    return VaultManager.get_folder_digest(profile, folder)
                res = VaultManager.search(profile, f_clean, target_folder=folder)
                if res and not res.startswith("No notes found") and "not configured" not in res:
                    return f"### Vault Search Results for '{folder}':\n{res}"

        # Clean conversational greetings & natural language search leads
        q = re.sub(r"^(?:hey|hi|hello|yo|good\s+\w+)\s*(?:\w+)?[\.\,\:\;–—\s\-]*", "", msg, flags=re.I).strip()
        q = re.sub(r"^(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?(?:how\s+about|what\s+about|do\s+we\s+have|is\s+there|tell\s+me\s+about|show\s+me|find|search|retrieve|check|look\s+(?:for|at)?|pick|get|pull)\s*", "", q, flags=re.I).strip()
        q = re.sub(r"^(?:(?:an?|the|some|any|random|my|our)\s+)?(?:obsidian\s+)?(?:vault\s+)?(?:daily\s+|historical\s+)?(?:notes?|journals?|entries|entry|reflections?|posts?|logs?)\s*(?:wayback|from|in|about|for|regarding|on|discussing|mentioning|talking\s+about)?\s*", "", q, flags=re.I).strip()
        target_q = re.split(r"[,.!?]", q)[0].strip()
        if target_q and len(target_q) >= 3 and has_intent:
            res = VaultManager.search(profile, target_q)
            if res and not res.startswith("No notes found") and "not configured" not in res:
                return f"### Vault Search Results for '{target_q}':\n{res}"
        return None

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
        target_model = self.model_overrides.get(target_handle.lower(), target_profile.get("model", "gemini/gemini-3.5-flash-lite"))
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

    def chat_stream(self, handle: str, user_message: str):
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

        # Build dynamic composite prompt & inject persistent pre-turn vault context
        system_prompt = self.pm.build_system_prompt(profile)
        vault_ctx = self._resolve_vault_context(profile, clean_input)
        if vault_ctx:
            self.active_vault_ctx[handle.lower()] = vault_ctx
        elif handle.lower() in self.active_vault_ctx and self.active_vault_ctx[handle.lower()]:
            vault_ctx = self.active_vault_ctx[handle.lower()]

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
            stream_val = bool(self.config.get("performance.stream", True))
            response = litellm.completion(**self._build_kwargs(target_model, profile, active_messages, stream=stream_val))
            full_reply = []
            for chunk in response:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full_reply.append(delta)
                    yield delta

            complete_text = "".join(full_reply)
            clean_text, badges = ActionProcessor.execute_actions(self.pm, handle, complete_text)
            has_worker = any("Sub-Agent Worker Report" in b for b in badges)
            assistant_record = (clean_text + ("\n\n" + "\n".join(badges) if badges else "")).strip()
            if badges:
                yield "\n\n" + "\n".join(badges)

            if has_worker:
                yield "\n\n"
                synth_msgs = list(active_messages) + [{"role": "assistant", "content": assistant_record}, {"role": "user", "content": "[System Directive: Synthesize the worker report above with findings and next steps.]"}]
                try:
                    synth_resp = litellm.completion(**self._build_kwargs(target_model, profile, synth_msgs, stream=True))
                    synth_reply = "".join([c.choices[0].delta.content or "" for c in synth_resp if c.choices[0].delta.content]).strip()
                    if synth_reply:
                        assistant_record += "\n\n" + synth_reply
                        yield synth_reply
                except Exception:
                    pass

            history.extend([{"role": "user", "content": user_message}, {"role": "assistant", "content": assistant_record}])
            self.histories[handle.lower()] = history[-(self.max_turns * 2):]
            self.archivist.trigger_background_extraction(handle, user_message, complete_text)
        except Exception as e:
            err = str(e)
            yield f"⚠️ **Local Model Offline ({target_model}):** Run `ollama serve`." if ("11434" in err or "Connection refused" in err) else f"⚠️ **Runtime Error ({target_model}):** {err}"
