"""
Multi-Model Persona Execution Engine for Sympose.
"""

import os, re, threading
from typing import Dict, List, Any, Optional
import litellm

from sympose.config import config_manager, DEFAULT_CHAT_MODEL
from sympose.profiles import ProfileManager
from sympose.memory import SessionArchivist
from sympose.commands import CommandInterceptor
from sympose.actions import ActionProcessor
from sympose.vault import VaultManager
from sympose.sessions import SessionManager


class PersonaEngine:
    """Executes multi-model AI completions with sliding context, vault context injection, and autonomic actions."""

    # Start of an autonomic retrieval tag. Once the model emits one of these it
    # cannot yet know the result, so everything it streams afterwards is a guess
    # — the visible stream is cut here and the runtime injects the real report.
    _RETRIEVAL_TAG_RE = re.compile(r"\[(?:ACTION:)?(?:SEARCH|WEB_SEARCH|SPAWN_WORKER)\b", re.I)

    # Local inference backends: with `vault_grounding: auto`, a persona on one of
    # these gets `strict` grounding (the runtime forces `vault_recall` rather
    # than trusting the model to emit the tag). Cloud models get `trust`.
    _LOCAL_MODEL_PREFIXES = (
        "ollama", "ollama_chat", "ollama_completion", "lm_studio",
        "text-completion-openai", "llamafile", "llama-cpp-python",
    )
    # A reply that asserts it is reporting the user's own vault content. If one
    # of these fires and no retrieval ran this turn, a strict-grounding persona
    # is fabricating — the reply is withheld.
    _VAULT_CLAIM_RE = re.compile(
        r"(what you (?:wrote|written|noted|said) about|here'?s (?:a |the )?summary of what you|"
        r"your (?:entry|note|journal entry|vault note)\b|in your vault[,\s]|from your vault\b|"
        r"you (?:describe|mention|write about) .{0,40}\bin (?:your|the) (?:vault|journal|notes?)\b)",
        re.I,
    )
    _NAME_STOP = frozenset({
        "certainly", "sure", "here", "your", "yours", "the", "would", "could",
        "sympose", "okay", "yes", "let", "what", "when", "how", "and", "but",
        "sub", "agent", "worker", "report", "task", "skills", "vault", "note",
        "damiro", "anais", "grace", "samantha",
    })

    def _grounding_mode(self, profile: Dict[str, Any], target_model: str) -> str:
        """`strict` → the runtime enforces vault retrieval itself; `trust` →
        rely on the model to emit `[SPAWN_WORKER: vault_recall]`. An explicit
        persona `vault_grounding: strict|trust` wins; otherwise `auto` derives it
        from the model (local backend or a localhost `api_base` → strict)."""
        explicit = str(profile.get("vault_grounding", "") or "").strip().lower()
        if explicit in ("strict", "trust"):
            return explicit
        default = str(self.config.get("vault.grounding_default", "auto") or "auto").strip().lower()
        if default in ("strict", "trust"):
            return default
        backend = str(target_model or "").split("/", 1)[0].strip().lower()
        api_base = str(profile.get("api_base", "") or "").lower()
        is_local = backend in self._LOCAL_MODEL_PREFIXES or any(
            h in api_base for h in ("localhost", "127.0.0.1", "0.0.0.0", ":11434")
        )
        return "strict" if is_local else "trust"

    @staticmethod
    def _depossess(word: str) -> str:
        return re.sub(r"['’]s?$", "", word).strip()

    @classmethod
    def _entity_guess(cls, *texts: str) -> str:
        """Best-effort name/subject of a recall request across a few candidate
        strings (current message, then recent history), for the strict-grounding
        forced retrieval. Returns '' when nothing looks like a subject."""
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
                if cand and cand.lower() not in cls._NAME_STOP:
                    return cand
            for w in re.findall(r"\b[A-Z][a-zA-Z’'-]{2,}\b", text):
                d = cls._depossess(w)
                if d and d.lower() not in cls._NAME_STOP:
                    return d
        return ""

    def __init__(self, profile_manager: ProfileManager, max_turns: Optional[int] = None):
        self.pm, self.config, self.archivist = profile_manager, config_manager, SessionArchivist(profile_manager)
        self.max_turns = max_turns or int(self.config.get("performance.max_context_turns", 15))
        self.histories: Dict[str, List[Dict[str, str]]] = {}
        self.active_sessions: Dict[str, str] = {}
        self.model_overrides: Dict[str, str] = {}
        self.active_vault_ctx: Dict[str, str] = {}
        # Guards mutation of the four dicts above. One PersonaEngine is shared
        # across every Slack daemon thread (one per concurrent in-flight
        # message), so check-then-act sequences on this state need to be atomic.
        self._lock = threading.RLock()

    def _get_history_key(self, handle: str, session_id: Optional[str] = None) -> str:
        return f"{handle.lower()}::{session_id}" if session_id else handle.lower()

    def get_history(self, handle: str, session_id: Optional[str] = None) -> List[Dict[str, str]]:
        with self._lock:
            return self.histories.setdefault(self._get_history_key(handle, session_id), [])

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

    def resume_session(self, handle: str, session_id: str) -> Optional[Dict[str, Any]]:
        h_low = handle.lower()
        session = SessionManager.load_session(session_id)
        if not session:
            return None
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
        with self._lock:
            self.active_sessions[h_low] = session_id
            self.histories[h_key] = hydrated
        return session

    def reset_history(self, handle: str, session_id: Optional[str] = None) -> None:
        with self._lock:
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

    def get_model_override(self, handle: str) -> Optional[str]:
        with self._lock:
            return self.model_overrides.get(handle.lower())

    def set_model_override(self, handle: str, model: str) -> None:
        with self._lock:
            self.model_overrides[handle.lower()] = model

    def clear_model_override(self, handle: str) -> Optional[str]:
        with self._lock:
            return self.model_overrides.pop(handle.lower(), None)

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
        kwargs = {"model": target_model, "messages": messages, "stream": stream, "timeout": float(self.config.get(to_key, 120.0 if is_loc else 30.0))}
        for pfx, key in (("gemini/", "GEMINI_API_KEY"), ("anthropic/", "ANTHROPIC_API_KEY"), ("openai/", "OPENAI_API_KEY"), ("openrouter/", "OPENROUTER_API_KEY")):
            if target_model.startswith(pfx) and os.getenv(key):
                kwargs["api_key"] = os.getenv(key)
        if "temperature" in profile: kwargs["temperature"] = profile["temperature"]
        if profile.get("api_base"): kwargs["api_base"] = profile["api_base"]
        if is_loc:
            # Per-persona residency override for local backends: persona YAML
            # `keep_alive` wins, else `performance.local_keep_alive`, else leave
            # it to the server-wide OLLAMA_KEEP_ALIVE env var. Accepts -1
            # (forever), 0 (unload now), or a duration string like "30m".
            ka = profile.get("keep_alive")
            if ka is None:
                ka = self.config.get("performance.local_keep_alive")
            if ka is not None:
                kwargs["keep_alive"] = ka
        return kwargs

    def spawn_sub_agent(self, target_handle: str, sub_prompt: str):
        target_profile = self.pm.get_profile(target_handle)
        if not target_profile:
            yield f"⚠️ Specialist agent `@{target_handle}` not found in profiles."
            return

        system_prompt = self.pm.build_system_prompt(target_profile)
        target_model = self.get_model_override(target_handle) or target_profile.get("model") or DEFAULT_CHAT_MODEL
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

    def _visible_stream(self, response: Any, sink: List[str]):
        """Yield model text for display, but stop the moment a retrieval tag
        (`[SEARCH …]` / `[SPAWN_WORKER …]`) begins: the runtime will inject the
        real report, so a weak local model that keeps 'reading out' the note it
        has not seen yet must not reach the user. The full raw text still lands
        in `sink[0]` for `ActionProcessor`. A short hold-back keeps a tag that
        is split across chunks from leaking its first characters."""
        HOLDBACK = 24
        buf: List[str] = []
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
            m = self._RETRIEVAL_TAG_RE.search(text)
            if m:
                if m.start() > emitted:
                    yield text[emitted:m.start()]
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
        # Retrieval itself stays outside the lock — it's the hot-path I/O this
        # session's caching work was aimed at, and must not serialize concurrent
        # chats across personas/threads behind one engine-wide lock.
        vault_ctx = VaultManager.resolve_turn_context(profile, clean_input)
        with self._lock:
            if vault_ctx:
                self.active_vault_ctx[h_key] = vault_ctx
            elif VaultManager.has_recall_intent(clean_input):
                # Fresh vault question, nothing retrieved: drop any carried-over
                # context so the model can't answer "pull up X" from a stale,
                # unrelated note. It must take the honest path (spawn a worker
                # or say it has no record).
                self.active_vault_ctx[h_key] = None
            elif h_key in self.active_vault_ctx and self.active_vault_ctx[h_key]:
                vault_ctx = self.active_vault_ctx[h_key]

        system_prompt = self.pm.build_system_prompt(profile)
        if vault_ctx:
            system_prompt += f"\n\n{vault_ctx}"

        history = self.get_history(handle, session_id=session_id)
        active_messages = [{"role": "system", "content": system_prompt}]
        active_messages.extend(history[-(self.max_turns * 2):])
        active_messages.append({"role": "user", "content": user_message})

        target_model = self.get_model_override(handle) or profile.get("model") or DEFAULT_CHAT_MODEL
        if litellm is None:
            yield "⚠️ LiteLLM is not installed. Run `pip install -r requirements.txt`."
            return

        strict = self._grounding_mode(profile, target_model) == "strict" and not vault_ctx

        try:
            stream_val = bool(self.config.get("performance.stream", True))
            response = litellm.completion(**self._build_kwargs(target_model, profile, active_messages, stream=stream_val))
            sink: List[str] = []
            held: List[str] = []
            for piece in self._visible_stream(response, sink):
                # strict-grounding personas hold the model's text until we know
                # whether it fabricated an un-retrieved vault answer.
                if strict:
                    held.append(piece)
                else:
                    yield piece

            complete_text = sink[0] if sink else ""
            clean_text, badges = ActionProcessor.execute_actions(self.pm, handle, complete_text, user_prompt=clean_input)
            has_worker = any("Sub-Agent Worker" in b or "Live Web Search Report" in b for b in badges)
            has_retrieval = has_worker or any("Web Search" in b for b in badges)

            forced_answer = None
            if strict and not has_worker:
                # The model neither had pre-turn context nor spawned a worker.
                # If a vault subject is in play, retrieve it ourselves; if it is
                # clearly reporting vault content anyway, withhold the guess.
                prev_asst = next((m["content"] for m in reversed(history) if m.get("role") == "assistant"), "")
                prev_user = next((m["content"] for m in reversed(history) if m.get("role") == "user"), "")
                affirm = bool(re.match(r"^(yes|yep|yeah|sure|ok(ay)?|please( do)?|go ahead|do it|go on|"
                                       r"continue|just summari[sz]e|summari[sz]e it)\b", clean_input, re.I))
                subj, had_leadin = VaultManager._extract_recall_subject(clean_input)
                if not (had_leadin or VaultManager.has_recall_intent(clean_input)):
                    subj = ""
                if not subj and affirm and re.search(r"\b(pull|retriev|check|look (up|at)|find|fetch|summari[sz]e)\b.{0,60}\b(entry|note|vault|journal)\b", prev_asst, re.I):
                    subj = self._entity_guess(prev_asst, prev_user)
                if not subj and self._VAULT_CLAIM_RE.search(clean_text):
                    subj = self._entity_guess(clean_input, prev_user, prev_asst)

                if subj:
                    _, fb = ActionProcessor.execute_actions(
                        self.pm, handle, f"[SPAWN_WORKER: vault_recall | {subj}]", user_prompt=clean_input)
                    if any("Sub-Agent Worker" in b for b in fb):
                        badges = fb + badges
                        has_worker = has_retrieval = True
                        clean_text = ""  # discard the model's un-retrieved answer
                elif self._VAULT_CLAIM_RE.search(clean_text):
                    forced_answer = ("I haven't actually pulled that from your vault yet — tell me the "
                                     "note or the name and I'll read it for you.")
                    clean_text = forced_answer

            if strict:
                # Emit what survived the check: the candid line, or the model's
                # own text when it did not need forcing.
                if forced_answer is not None:
                    yield forced_answer
                elif not (has_worker and not "".join(held).strip()):
                    lead = "".join(held) if clean_text else ""
                    if lead:
                        yield lead

            if has_retrieval and not forced_answer:
                # A retrieval tag ran: the runtime supplies the ground truth via
                # the badge/synthesis below, so anything the model wrote around
                # its own tag is a pre-emptive guess. Keep only a short lead-in
                # (up to the first tag, minus any fabricated note body).
                m = self._RETRIEVAL_TAG_RE.search(complete_text)
                lead = complete_text[:m.start()] if m else clean_text
                lead = ActionProcessor.strip_action_tags(lead)
                clean_text = re.split(r"\n\s*(?:#{1,6}\s|>\s|-{3,}\s*$|```)", lead, maxsplit=1)[0].strip()
            assistant_record = (clean_text + ("\n\n" + "\n".join(badges) if badges else "")).strip()
            if badges:
                yield "\n\n" + "\n".join(badges)

            # Always synthesise a grounded final answer from the worker report:
            # the model's pre-tag text was trimmed as a guess, and the report now
            # carries the verbatim note text (see actions.py READ_NOTE) for it to
            # quote — on terminal and Slack alike.
            if has_worker:
                yield "\n\n"
                synth_msgs = list(active_messages) + [{"role": "assistant", "content": assistant_record}, {"role": "user", "content": "[System Directive: Using ONLY the report above as ground truth, give the user the direct answer. Quote note text verbatim; do not add any detail that is not in the report.]"}]
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
            with self._lock:
                self.histories[h_key] = history[-(self.max_turns * 2):]
            meta = SessionManager.append_turn(curr_session_id, handle, user_message, assistant_record)
            if meta and meta.get("turns_count") == 3:
                SessionManager.generate_smart_title_async(curr_session_id, handle, history[-6:], self.config)
            self.archivist.trigger_background_extraction(handle, user_message, complete_text)
        except Exception as e:
            err = str(e)
            yield f"⚠️ **Local Model Offline ({target_model}):** Run `ollama serve`." if ("11434" in err or "Connection refused" in err) else f"⚠️ **Runtime Error ({target_model}):** {err}"
