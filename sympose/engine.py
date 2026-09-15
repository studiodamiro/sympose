"""
Multi-Model Persona Execution Engine for Sympose.
"""

import logging
import re
import threading
from collections.abc import Callable
from typing import Any

import litellm

log = logging.getLogger(__name__)

from sympose.actions import ActionProcessor
from sympose.commands import CommandInterceptor
from sympose.config import DEFAULT_CHAT_MODEL, config_manager
from sympose.memory import SessionArchivist
from sympose.model_router import resolve_turn_model
from sympose.models import resolve_api_key
from sympose.profiles import ProfileManager
from sympose.session_recall import has_session_recall_intent
from sympose.sessions import SessionManager
from sympose.vault import VaultManager


class PersonaEngine:
    """Executes multi-model AI completions with sliding context, vault context injection, and autonomic actions."""

    # Start of an autonomic retrieval tag. Once the model emits one of these it
    # cannot yet know the result, so everything it streams afterwards is a guess
    # — the visible stream is cut here and the runtime injects the real report.
    _RETRIEVAL_TAG_RE = re.compile(
        r"\[(?:ACTION:)?(?:SEARCH|WEB_SEARCH|SPAWN_SUB_AGENT)\b", re.IGNORECASE
    )

    # Every autonomic action tag, not just retrieval ones - built from
    # ActionProcessor's own list so it can't quietly drift out of sync with
    # it. A tag's bracket syntax is internal wire format; without this, a
    # non-retrieval tag (WRITE_NOTE, REMEMBER, CONFIG_SET, ...) just sits in
    # _visible_stream's holdback buffer and gets unconditionally flushed
    # once the stream ends, leaking its raw `[WRITE_NOTE: ...]` text into
    # what the user actually sees, right next to the clean confirmation
    # badge for the same action.
    _ANY_ACTION_TAG_RE = re.compile(
        r"\[(?:ACTION:)?(?:" + "|".join(ActionProcessor.TAG_NAMES) + r")\b",
        re.IGNORECASE,
    )

    # Cloud chat APIs enforce the assistant/user turn boundary server-side.
    # Local backends only stop where the model's own template's stop token
    # fires — a mismatched or broken template (seen on some community
    # fine-tunes) lets generation run past the reply into a hallucinated
    # continuation. These are model-agnostic markers for that continuation,
    # applied as a `stop` list so it's cut regardless of the local model's
    # own template correctness.
    _LOCAL_RUNAWAY_STOP_SEQUENCES = (
        "\n### User:",
        "\n### Assistant:",
        "\nUser:",
        "\nYou (to",
    )

    # Local inference backends: with `vault_grounding: auto`, a persona on one of
    # these gets `strict` grounding (the runtime forces `vault_recall` rather
    # than trusting the model to emit the tag). Cloud models get `trust`.
    _LOCAL_MODEL_PREFIXES = (
        "ollama",
        "ollama_chat",
        "ollama_completion",
        "lm_studio",
        "text-completion-openai",
        "llamafile",
        "llama-cpp-python",
    )
    # A reply that asserts it is reporting the user's own vault content. If one
    # of these fires and no retrieval ran this turn, a strict-grounding persona
    # is fabricating — the reply is withheld. The last alternative is a
    # structural signal rather than a phrase: a vault-shaped file path (e.g.
    # "General/Personal Philosophy.md" in a fabricated "Source:" citation)
    # can only be legitimate here if a retrieval actually produced it, and
    # this regex is only ever consulted when it didn't (see the `not
    # has_sub_agent` guard around its call sites) — so a bare path match is
    # as damning as the wording-based alternatives, without having to
    # enumerate every way a model can dress up an invented note.
    _VAULT_CLAIM_RE = re.compile(
        r"(what you (?:wrote|written|noted|said) about|here'?s (?:a |the )?summary of what you|"
        r"your (?:entry|note|journal entry|vault note)\b|in your vault\b|from your vault\b|"
        r"you (?:describe|mention|write about) .{0,40}\bin (?:your|the) (?:vault|journal|notes?)\b|"
        r"[\w][\w \-]*(?:/[\w][\w \-]*)+\.md\b)",
        re.IGNORECASE,
    )
    _NAME_STOP = frozenset(
        {
            "certainly",
            "sure",
            "here",
            "your",
            "yours",
            "the",
            "would",
            "could",
            "sympose",
            "okay",
            "yes",
            "let",
            "what",
            "when",
            "how",
            "and",
            "but",
            "sub",
            "agent",
            "report",
            "task",
            "skills",
            "vault",
            "note",
            "damiro",
            "anais",
            "grace",
            "samantha",
            "hello",
            "hi",
            "hey",
            "thanks",
            "thank",
            "today",
            "whether",
            "since",
            "well",
            # Contractions are never entities regardless of position - a
            # sentence-boundary check alone misses one that follows a comma
            # ("Yes, I'm here") rather than a full stop. _depossess() strips
            # a trailing 's ('it's' -> 'it') before this set is checked, so
            # an 's-contraction belongs here in its already-stripped form,
            # not as the literal "word's" spelling.
            "i'm",
            "i'll",
            "i've",
            "i'd",
            "you're",
            "you'll",
            "you've",
            "we're",
            "we'll",
            "we've",
            "they're",
            "it",
            "that",
            "there",
            "who",
        }
    )

    @staticmethod
    def _is_full_body_vault_ctx(vault_ctx: str | None) -> bool:
        """Pre-turn `vault_ctx` (VaultManager.resolve_turn_context) comes in two
        shapes: a note's full verbatim body (every such payload carries the
        literal "Exact Content" marker in its header — see vault.py's
        `### Ground-Truth ... (... Exact Content):` returns), or a thin digest
        (a search-results list, a backlink index, the structural manifest) that
        only gives titles/snippets/counts. Only the former is strong enough
        grounding to suspend strict mode's *retrieval-enforcement* fallback
        for the turn — live bug: a "thoughts" search digest (title + one-line
        snippet per note) was enough to turn strict off entirely, and the
        model filled the gap between snippet and full note with an invented
        essay that nothing caught. Citation verification (below) still runs
        on a full body — a real note being available doesn't guarantee the
        model actually used it."""
        return bool(vault_ctx) and "Exact Content" in vault_ctx

    # Same structural shape as the last `_VAULT_CLAIM_RE` alternative, reused
    # here to extract every note path a piece of text names - both the ones
    # the model's reply claims to be quoting and the ones actually present in
    # the ground-truth it was handed - so the two can be compared.
    _VAULT_PATH_TOKEN_RE = re.compile(
        r"[\w][\w \-]*(?:/[\w][\w \-]*)+\.(?:md|markdown|txt)\b", re.IGNORECASE
    )

    @classmethod
    def _vault_ctx_citation_mismatch(cls, clean_text: str, vault_ctx: str | None) -> bool:
        """True when `clean_text` names a vault note path that appears
        nowhere in the ground-truth `vault_ctx` actually injected this turn —
        i.e. the model swapped in an invented path instead of the real one it
        was given. Live bug: handed the real content of
        `Daily/2023/05-May/2023-05-17.md`, gemma4:e4b answered with a
        plausible-looking but entirely fictional `Thoughts/hmmm.md` instead
        of quoting what it actually had. Silent (False) when the reply names
        no path at all — that prose-only case isn't checkable without a
        second model call to compare meaning, which conflicts with Sympose's
        round-trip-frugal design, so it stays a known residual gap rather
        than something this catches."""
        if not vault_ctx:
            return False
        reply_paths = {p.lower() for p in cls._VAULT_PATH_TOKEN_RE.findall(clean_text)}
        if not reply_paths:
            return False
        ctx_paths = {p.lower() for p in cls._VAULT_PATH_TOKEN_RE.findall(vault_ctx)}
        return not (reply_paths & ctx_paths)

    @staticmethod
    def _strip_vault_ctx_headers(vault_ctx: str) -> str:
        """Drops the internal `### Ground-Truth ...` bookkeeping headers from
        a resolved vault context, leaving just the real note body/bodies to
        show the user directly when the model's own retelling of them can't
        be trusted."""
        return re.sub(r"(?m)^### Ground-Truth[^\n]*\n?", "", vault_ctx).strip()

    def _grounding_mode(self, profile: dict[str, Any], target_model: str) -> str:
        """`strict` → the runtime enforces vault retrieval itself; `trust` →
        rely on the model to emit `[SPAWN_SUB_AGENT: vault_recall]`. An explicit
        persona `vault_grounding: strict|trust` wins; otherwise `auto` derives it
        from the model (local backend or a localhost `api_base` → strict)."""
        explicit = str(profile.get("vault_grounding", "") or "").strip().lower()
        if explicit in ("strict", "trust"):
            return explicit
        default = (
            str(self.config.get("vault.grounding_default") or "auto").strip().lower()
        )
        if default in ("strict", "trust"):
            return default
        backend = str(target_model or "").split("/", 1)[0].strip().lower()
        api_base = str(profile.get("api_base", "") or "").lower()
        is_local = backend in self._LOCAL_MODEL_PREFIXES or any(
            h in api_base for h in ("localhost", "127.0.0.1", "0.0.0.0", ":11434")
        )
        return "strict" if is_local else "trust"

    @staticmethod
    def _build_session_history_digest(
        handle: str, exclude_session_id: str | None
    ) -> str:
        """Deterministic, zero-round-trip answer to 'what did we do last
        session?': the persona's own local JSONL history (SessionManager,
        ADR-054) already holds exactly this, so it's injected as ground-truth
        context the same way vault_ctx is — no sub-agent, no extra LLM call.
        Always returns a non-empty block when session_recall intent fires, so
        the model has a definitive answer instead of guessing or defaulting
        to a vault crawl (which is a different store entirely and, per
        `session.exit_behavior`, may hold nothing anyway)."""
        sessions = [
            s
            for s in SessionManager.list_sessions(handle=handle, limit=6)
            if s.get("session_id") != exclude_session_id
        ][:3]
        if not sessions:
            return (
                "### Local Sympose Session History:\n"
                "No prior Sympose session is recorded locally for this persona "
                "yet. This is NOT the same as the Obsidian vault — do not spawn "
                "a vault_recall sub-agent for this; just say so."
            )
        lines = [
            f'- "{s.get("title", "Untitled Session")}" — {s.get("relative_time", "")} '
            f'({s.get("turns_count", 0)} turns)'
            for s in sessions
        ]
        return (
            "### Local Sympose Session History (most recent first):\n"
            + "\n".join(lines)
            + "\n\nThis is Sympose's own local conversation history, not the "
            "Obsidian vault — answer from it directly, do not spawn a "
            "vault_recall sub-agent for this question."
        )

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
            # Fallback: any other Capitalised word — but only mid-sentence.
            # Sentence-initial capitalisation is just English grammar (or a
            # contraction like "I'll"/"I'm"), not an entity signal, and was
            # handing back words like "Hello" or "I'll" from ordinary small
            # talk with no real subject in it at all.
            for cm in re.finditer(r"\b[A-Z][a-zA-Z’'-]{2,}\b", text):
                start = cm.start()
                if start == 0 or re.search(r"[.!?]\s$", text[max(0, start - 2) : start]):
                    continue
                d = cls._depossess(cm.group(0))
                if d and d.lower() not in cls._NAME_STOP:
                    return d
        return ""

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
        backend = str(target_model or "").split("/", 1)[0].strip().lower()
        api_base = str(profile.get("api_base", "") or "").lower()
        is_loc = backend in self._LOCAL_MODEL_PREFIXES or any(
            h in api_base for h in ("localhost", "127.0.0.1", "0.0.0.0", ":11434")
        )
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
        strict grounding exists to guard against."""
        local_model = str(profile.get("local_model") or "").strip()
        if (
            not local_model
            or self.get_model_override(handle)
            or vault_ctx
            or VaultManager.has_recall_intent(clean_input)
        ):
            return target_model, False
        keep_alive = self._resolve_keep_alive(profile, local_model)
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
            for item in cmd_gen:
                yield item
            return

        nat_match = re.search(
            r"^(?:(?:hey|hi|hello)?\s*(?:@?\w+[,:]?\s*)?)?(?:please\s+)?remember\s+(?:that\s+|to\s+|:\s+)?(.+)$",
            clean_input,
            re.IGNORECASE,
        )
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
                # unrelated note. It must take the honest path (spawn a sub-agent
                # or say it has no record).
                self.active_vault_ctx[h_key] = None
            elif self.active_vault_ctx.get(h_key):
                # Reusing a prior turn's resolved context — re-read a
                # single-note reference fresh rather than replaying a frozen
                # copy that may no longer match the file on disk.
                vault_ctx = VaultManager.refresh_note_context(
                    profile, self.active_vault_ctx[h_key]
                )
                self.active_vault_ctx[h_key] = vault_ctx

        system_prompt = self.pm.build_system_prompt(profile)
        if vault_ctx:
            system_prompt += f"\n\n{vault_ctx}"
        if has_session_recall_intent(clean_input):
            system_prompt += "\n\n" + self._build_session_history_digest(
                handle, curr_session_id
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
            held: list[str] = []
            for piece in self._visible_stream(response, sink):
                # strict-grounding personas hold the model's text until we know
                # whether it fabricated an un-retrieved vault answer, or (when
                # a real note was already given) cited a different one than
                # the one it actually has.
                if hold_stream:
                    held.append(piece)
                else:
                    yield piece

            complete_text = sink[0] if sink else ""
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
            if verify_ctx and not has_sub_agent and self._vault_ctx_citation_mismatch(
                clean_text, vault_ctx
            ):
                # A real note was handed to the model this turn and it named
                # a different one instead of quoting what it actually had -
                # discard the invented reply and show the real note directly
                # rather than trusting a second attempt to do better.
                clean_text = (
                    "That's not what I actually have — here's the real note:\n\n"
                    + self._strip_vault_ctx_headers(vault_ctx or "")
                )
                held = [clean_text]

            if strict and not has_sub_agent:
                # The model neither had pre-turn context nor spawned a sub-agent.
                # If a vault subject is in play, retrieve it ourselves; if it is
                # clearly reporting vault content anyway, withhold the guess.
                prev_asst = next(
                    (
                        m["content"]
                        for m in reversed(history)
                        if m.get("role") == "assistant"
                    ),
                    "",
                )
                prev_user = next(
                    (
                        m["content"]
                        for m in reversed(history)
                        if m.get("role") == "user"
                    ),
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
                if (
                    not subj
                    and affirm
                    and re.search(
                        r"\b(pull|retriev|check|look (up|at)|find|fetch|summari[sz]e)\b.{0,60}\b(entry|note|vault|journal)\b",
                        prev_asst,
                        re.IGNORECASE,
                    )
                ):
                    subj = self._entity_guess(prev_asst, prev_user)
                if not subj and self._VAULT_CLAIM_RE.search(clean_text):
                    # The claim just made is in clean_text itself (e.g. "here's
                    # your entry about X") — search it first, not the *previous*
                    # turn's assistant text, which has no bearing on this claim
                    # and can hand back an unrelated word from earlier small talk.
                    subj = self._entity_guess(clean_text, clean_input, prev_user)

                if subj:
                    _, fb = ActionProcessor.execute_actions(
                        self.pm,
                        handle,
                        f"[SPAWN_SUB_AGENT: vault_recall | {subj}]",
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

            if has_retrieval and not forced_answer:
                # A retrieval tag ran: the runtime supplies the ground truth via
                # the badge/synthesis below, so anything the model wrote around
                # its own tag is a pre-emptive guess. Keep only a short lead-in
                # (up to the first tag, minus any fabricated note body).
                m = self._RETRIEVAL_TAG_RE.search(complete_text)
                lead = complete_text[: m.start()] if m else clean_text
                lead = ActionProcessor.strip_action_tags(lead)
                clean_text = re.split(
                    r"\n\s*(?:#{1,6}\s|>\s|-{3,}\s*$|```)", lead, maxsplit=1
                )[0].strip()
            assistant_record = (
                clean_text + ("\n\n" + "\n".join(badges) if badges else "")
            ).strip()
            if badges:
                yield "\n\n" + "\n".join(badges)

            # Always synthesise a grounded final answer from the sub-agent report:
            # the model's pre-tag text was trimmed as a guess, and the report now
            # carries the verbatim note text (see actions.py READ_NOTE) for it to
            # quote — on terminal and Slack alike.
            if has_sub_agent:
                yield "\n\n"
                synth_msgs = list(active_messages) + [
                    {"role": "assistant", "content": assistant_record},
                    {
                        "role": "user",
                        "content": "[System Directive: Using ONLY the report above as ground truth, give the user the direct answer. Quote note text verbatim; do not add any detail that is not in the report.]",
                    },
                ]
                try:
                    synth_resp = litellm.completion(
                        **self._build_kwargs(
                            target_model, profile, synth_msgs, stream=True
                        )
                    )
                    synth_reply = "".join(
                        [
                            c.choices[0].delta.content or ""
                            for c in synth_resp
                            if c.choices[0].delta.content
                        ]
                    ).strip()
                    if synth_reply:
                        assistant_record += "\n\n" + synth_reply
                        yield synth_reply
                except Exception as e:
                    log.debug("Forced synthesis stream failed: %s", e)

            history.extend(
                [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_record},
                ]
            )
            h_key = self._get_history_key(handle, session_id)
            with self._lock:
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
        except Exception as e:
            err = str(e)
            yield (
                f"⚠️ **Local Model Offline ({target_model}):** Run `ollama serve`."
                if ("11434" in err or "Connection refused" in err)
                else f"⚠️ **Runtime Error ({target_model}):** {err}"
            )
