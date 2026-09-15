"""
Ephemeral Sub-Agent Engine & Multi-Turn Tool Execution Loop for Sympose.
Executes isolated sub-agent tasks loaded with specific skills and MCP servers without polluting main persona context.
"""

import json
import logging
import os
import re
from collections.abc import Callable, Generator
from typing import Any

import litellm

from sympose.config import DEFAULT_SUB_AGENT_MODEL, config_manager
from sympose.mcp import MCPClient, mcp_registry
from sympose.models import resolve_api_key
from sympose.native_tools import NativeTools
from sympose.profiles import ProfileManager
from sympose.prompt_assets import load_prompt
from sympose.skills import skill_manager
from sympose.vault import VAULT_PATH_TOKEN_RE, VaultManager

log = logging.getLogger(__name__)

MAX_TOOL_OUTPUT_CHARS = 20000

# Live bug: a vault_read sub-agent had no tool that actually does what its
# own skill was for - only generic run_command/read_file - so every search
# or "pick a random note" request got reconstructed by hand from grep/find/
# shuf, burning tool-call budget on work Sympose's own vault layer already
# does deterministically (search_structured's SQLite FTS index,
# get_random_sample_notes' folder sampling). These wrap those directly so a
# sub-agent gets one structured call instead of composing shell one-liners.
_VAULT_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "vault_search",
            "description": (
                "Full-text search over the indexed vault, ranked, with "
                "snippets. Use for any keyword, topic, date, or tag lookup "
                "instead of grep."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keyword(s), a date, or a tag to search for.",
                    },
                    "folder": {
                        "type": "string",
                        "description": "Optional: restrict the search to one top-level vault folder.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results to return (default 10).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vault_sample",
            "description": (
                "Returns the real, full content of one or more randomly "
                "sampled notes from a vault folder in a single call - use "
                "whenever the request names a folder without naming a "
                "specific note ('pick a random note', 'surprise me'). No "
                "separate read step needed afterward."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": "The vault folder to sample from.",
                    },
                    "count": {
                        "type": "integer",
                        "description": "How many notes to sample (default 1).",
                    },
                },
                "required": ["folder"],
            },
        },
    },
]


class SubAgentTask:
    """Specification for an isolated, ephemeral sub-agent execution."""

    def __init__(
        self,
        task_prompt: str,
        skills: list[str] | None = None,
        mcp_servers: list[str] | None = None,
        model: str | None = None,
        temperature: float = 0.1,
        max_tool_turns: int | None = None,
        parent_agent: str = "orchestrator",
    ):
        self.task_prompt = task_prompt.strip()
        self.skills = skills or []
        self.mcp_servers = mcp_servers or []
        self.model = model
        self.temperature = temperature
        default_turns = int(
            config_manager.get("performance.max_sub_agent_tool_turns", 8)
        )
        self.max_tool_turns = (
            max_tool_turns if max_tool_turns is not None else default_turns
        )
        self.parent_agent = parent_agent


class SubAgentEngine:
    """Executes single/multi-turn sub-agent runs with tool calling and skill playbooks."""

    # ------------------------------------------------------------------ #
    #  Shared setup helpers                                                #
    # ------------------------------------------------------------------ #

    @classmethod
    def _build_sub_agent_context(
        cls, task: SubAgentTask
    ) -> tuple[
        str,  # system_prompt
        str,  # target_model
        list[dict[str, Any]],  # initial messages
        dict[str, MCPClient],  # active_clients
        dict[str, MCPClient],  # tool_to_client
        list[dict[str, Any]],  # all_litellm_tools
        list[str] | None,  # allowed_dirs
        dict[str, Any] | None,  # parent_prof
    ]:
        """Builds the shared execution context for both streaming and non-streaming sub-agents."""
        skills_text = skill_manager.format_skills_for_prompt(task.skills)

        # Resolve parent agent sandbox whitelist
        pm = ProfileManager()
        parent_prof = pm.get_profile(task.parent_agent)
        allowed_dirs = (
            VaultManager.get_allowed_dirs(parent_prof) if parent_prof else None
        )

        # Resolve MCP Clients & Tools + Native Built-in Tools
        active_clients: dict[str, MCPClient] = {}
        tool_to_client: dict[str, MCPClient] = {}
        all_litellm_tools: list[dict[str, Any]] = list(NativeTools.NATIVE_SCHEMAS)

        resolved_mcp_servers = list(task.mcp_servers)
        for s_name in task.skills:
            skill = skill_manager.get_skill(s_name)
            if skill and skill.mcp_servers:
                for s in skill.mcp_servers:
                    if s not in resolved_mcp_servers:
                        resolved_mcp_servers.append(s)

        for server_name in resolved_mcp_servers:
            client = mcp_registry.get_client(server_name)
            if client and client.start():
                active_clients[server_name] = client
                for t in client.get_litellm_tools():
                    tool_name = t["function"]["name"]
                    tool_to_client[tool_name] = client
                    all_litellm_tools.append(t)
            elif server_name not in ("shell", "git", "native"):
                log.debug(
                    "SubAgentEngine: could not connect to MCP server [%s]",
                    server_name,
                )

        # Load system prompt template
        mv = os.getenv("MASTER_VAULT_PATH")
        env_lines = [f"- Workspace Directory: `{os.getcwd()}`"] + (
            [f"- Obsidian Vault Directory: `{mv}`"] if mv else []
        )
        tmpl = load_prompt(
            "sub_agent_system.md",
            "You are an ephemeral Sub-Agent in Sympose on macOS dispatched by parent agent @{{parent_agent}}.\n\n"
            "### RUNTIME ENVIRONMENT:\n{{environment}}\n\n"
            "### UNIVERSAL OPERATIONAL DIRECTIVES:\n"
            "1. GROUND-TRUTH EXECUTION: Use tools directly.\n"
            "2. ZERO HAND-WAVING: Output factual deliverables.\n"
            "3. RAPID COMPLETION.",
        )

        system_prompt = tmpl.replace("{{parent_agent}}", task.parent_agent).replace(
            "{{environment}}", "\n".join(env_lines)
        )
        if skills_text:
            system_prompt += f"\n\n{skills_text}"

        # ADR-078.7: hand a vault-skilled sub-agent the structural map so it
        # navigates from it instead of shelling out to find/ls/wc. No-op when
        # `vault.manifest.enabled` is off or no manifest exists yet.
        if any(s in ("vault_read", "vault_write") for s in task.skills):
            try:
                manifest = VaultManager.get_manifest()
                if manifest and manifest.get("nodes"):
                    system_prompt += "\n\n" + VaultManager.format_manifest_digest(
                        manifest
                    )
            except Exception:
                log.debug(
                    "SubAgentEngine: manifest digest injection failed", exc_info=True
                )

        # Search/sample the vault deterministically instead of reconstructing
        # it from find/grep/shuf every time - see _VAULT_TOOL_SCHEMAS.
        if "vault_read" in task.skills:
            all_litellm_tools.extend(_VAULT_TOOL_SCHEMAS)

        # Live bug: a sub-agent spawned to recall "our favorite game" had no
        # way to know the parent persona's memory already spells out exactly
        # what that means ("favorite game is Vault Roulette - pull a random
        # note and discuss it") - it never receives the parent's working
        # memory at all, so it was left to reconstruct the meaning from
        # scratch via blind grep/find sweeps, which wandered into unrelated
        # directories and still landed on a guessed, mismatched note. Handing
        # it the same working-memory file the parent already has closes that
        # gap at the source instead of asking it to re-derive a fact that was
        # one read away. Appended last (same "lost in the middle" reasoning
        # as build_system_prompt's own placement) since it's the block the
        # very next tool call needs to have fresh in view.
        if parent_prof:
            persona_mem = pm.get_persona_memory(parent_prof)
            if persona_mem:
                system_prompt += (
                    "\n\n### Parent Persona's Working Memory\n"
                    "If the task below references something a fact here "
                    "already covers (a nickname for an activity, a "
                    "preference, a running joke), that fact is the answer - "
                    "use it directly instead of searching for or guessing at "
                    "what the term means.\n\n"
                    f"{persona_mem}"
                )

        # Resolve model: task override → skill recommendation → env default
        target_model = task.model
        if not target_model:
            for s_name in task.skills:
                s_obj = skill_manager.get_skill(s_name)
                if s_obj and s_obj.recommended_models:
                    target_model = s_obj.recommended_models[0]
                    break
        target_model = target_model or DEFAULT_SUB_AGENT_MODEL

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task.task_prompt},
        ]

        return (
            system_prompt,
            target_model,
            messages,
            active_clients,
            tool_to_client,
            all_litellm_tools,
            allowed_dirs,
            parent_prof,
        )

    @staticmethod
    def _inject_api_key(kwargs: dict[str, Any], target_model: str) -> None:
        """Injects the correct API key into litellm kwargs based on model provider prefix."""
        api_key = resolve_api_key(target_model)
        if api_key:
            kwargs["api_key"] = api_key

    @staticmethod
    def _inject_timeout(kwargs: dict[str, Any]) -> None:
        """Without an explicit value, this call had no timeout at all and
        could hang on litellm's own ambiguous default - live symptom:
        "Connection timed out after None seconds", the tell-tale sign
        nothing real was ever configured for it. Uses its own dedicated
        `sub_agent.request_timeout` rather than the chat path's local/cloud
        split (`performance.*_request_timeout`): those bound a live,
        streamed reply's TTFT, but a sub-agent's report is delivered as one
        block once its whole tool-calling loop finishes, so there's no TTFT
        reason to use the short cloud timeout even when its own model
        happens to be a cloud one - same reasoning as compactor.py's own
        background work using the generous timeout regardless of backend."""
        kwargs["timeout"] = float(config_manager.get("sub_agent.request_timeout"))

    @staticmethod
    def _run_vault_tool(
        t_name: str, args_dict: dict[str, Any], profile: dict[str, Any] | None
    ) -> tuple[bool, str]:
        """Dispatches `vault_search`/`vault_sample` - the deterministic vault
        primitives from _VAULT_TOOL_SCHEMAS - against the parent persona's
        own sandbox. Lives here rather than in NativeTools.execute because
        these need the full persona `profile` (for get_allowed_dirs, ignore
        folders, etc.), not just a bare `allowed_dirs` list."""
        if not profile:
            return False, "No parent persona profile resolved for this sub-agent."
        if t_name == "vault_search":
            query = str(args_dict.get("query", "")).strip()
            if not query:
                return False, "A `query` is required."
            folder = args_dict.get("folder") or None
            max_results = int(args_dict.get("max_results") or 10)
            results = VaultManager.search_structured(
                profile, query, target_folder=folder, max_results=max_results
            )
            if not results:
                return True, f"No matches for '{query}'."
            return True, VaultManager.format_search_digest(query, results)
        if t_name == "vault_sample":
            folder = str(args_dict.get("folder", "")).strip()
            if not folder:
                return False, "A `folder` is required."
            count = int(args_dict.get("count") or 1)
            payload = VaultManager.get_random_sample_notes(profile, folder, count)
            if not payload:
                return False, f"No notes found in `{folder}/`."
            return True, payload
        return False, f"Unknown vault tool `{t_name}`."

    @staticmethod
    def _dispatch_tool_call(
        tc: Any,
        tool_to_client: dict[str, MCPClient],
        allowed_dirs: list[str] | None,
        profile: dict[str, Any] | None = None,
    ) -> tuple[str, str, str, bool, str, dict[str, Any]]:
        """Parses a tool_call object and executes it. Returns (call_id, t_name, arg_summary, ok, tool_res, args_dict)."""
        fn = tc.function if hasattr(tc, "function") else tc.get("function", {})
        call_id = tc.id if hasattr(tc, "id") else tc.get("id", "call_1")
        t_name = fn.name if hasattr(fn, "name") else fn.get("name", "")
        raw_args = fn.arguments if hasattr(fn, "arguments") else fn.get("arguments", {})

        if isinstance(raw_args, str):
            try:
                args_dict = json.loads(raw_args)
            except Exception:
                args_dict = {}
        else:
            args_dict = raw_args or {}

        if not isinstance(args_dict, dict):
            args_dict = {}

        arg_summary = ", ".join(
            f"{k}={v}"
            for k, v in args_dict.items()
            if k in ("path", "query", "command", "file_path", "folder", "count")
        )

        if t_name in ("run_command", "read_file", "web_search"):
            ok, tool_res = NativeTools.execute(
                t_name, args_dict, allowed_dirs=allowed_dirs
            )
        elif t_name in ("vault_search", "vault_sample"):
            ok, tool_res = SubAgentEngine._run_vault_tool(t_name, args_dict, profile)
        else:
            client = tool_to_client.get(t_name)
            if client:
                ok, tool_res = client.call_tool(t_name, args_dict)
            else:
                ok, tool_res = (
                    False,
                    f"Tool `{t_name}` not registered with active MCP servers.",
                )

        if len(tool_res) > MAX_TOOL_OUTPUT_CHARS:
            tool_res = (
                tool_res[:MAX_TOOL_OUTPUT_CHARS]
                + "\n...[Output truncated for brevity]..."
            )

        return call_id, t_name, arg_summary, ok, tool_res, args_dict

    # Appended on the sub-agent's final allowed turn so it wraps up instead of
    # spending the turn on another tool call.
    _LAST_TURN_NUDGE = (
        "[System: this is your final turn — no more tool calls. Synthesise the "
        "answer now from the tool results already gathered. Quote note text "
        "verbatim; if the results don't cover the task, say exactly what is missing.]"
    )

    @classmethod
    def _forced_synthesis(
        cls, messages: list[dict[str, Any]], target_model: str, task: "SubAgentTask"
    ) -> str:
        """Backstop when the tool loop exhausts its budget mid-search: one more
        call with tools disabled, so the notes already read (they are in the
        transcript) still produce a grounded answer instead of a bare failure."""
        try:
            kwargs: dict[str, Any] = {
                "model": target_model,
                "messages": messages
                + [{"role": "user", "content": cls._LAST_TURN_NUDGE}],
                "temperature": task.temperature,
                "stream": False,
                "tool_choice": "none",
            }
            cls._inject_api_key(kwargs, target_model)
            cls._inject_timeout(kwargs)
            return (
                litellm.completion(**kwargs).choices[0].message.content or ""
            ).strip()
        except Exception:
            return ""

    # Live bug (caught by a real ollama/gemma4:e4b run, not just reasoning
    # about the code): asked to pull a random Daily note and read it, it
    # never called read_file, then confidently invented a full multi-section
    # diary entry for whatever bare filename `find` had turned up - citing it
    # as `2022-08-29.md` and **2022-08-29.md**, neither of which
    # VAULT_PATH_TOKEN_RE matches, since that pattern requires a folder
    # prefix (`Daily/2022-08-29.md`) and a bare filename has none. Markdown
    # backtick/bold wrapping is itself a structural signal - independent of
    # wording - that a model is presenting a bare filename as a specific
    # document citation rather than using it incidentally in prose, so it's
    # what closes the gap here without resorting to a phrase list.
    _BARE_CITED_FILENAME_RE = re.compile(
        r"[`*]{1,3}([\w][\w \-]*\.(?:md|markdown|txt))[`*]{1,3}", re.IGNORECASE
    )

    # A local model reads a file via `run_command` (`cat`, `sed -n`, `head`,
    # an inline `python -c "open(...)"`...) at least as often as via the
    # dedicated read_file tool - live-observed in the same run that
    # motivated the check above. Whichever utility it used, the literal
    # filename has to appear in the command string for that command to have
    # actually retrieved that file's content, so matching on the command
    # text itself (not on which specific tool ran it) generalizes to any of
    # them without hardcoding a list of "reading" commands.
    _COMMAND_FILENAME_RE = re.compile(
        r"[\w][\w./\-]*\.(?:md|markdown|txt)\b", re.IGNORECASE
    )

    @classmethod
    def _register_read(
        cls,
        t_name: str,
        ok: bool,
        args_dict: dict[str, Any],
        tool_res: str,
        read_paths: set[str],
    ) -> None:
        """Records what this tool call actually retrieved, if anything, for
        `_content_unread` to check a synthesis against."""
        if not ok:
            return
        if t_name == "read_file":
            p = str(args_dict.get("path", "")).strip()
            if p:
                read_paths.add(p)
        elif t_name == "run_command":
            cmd = str(args_dict.get("command", ""))
            read_paths.update(cls._COMMAND_FILENAME_RE.findall(cmd))
        elif t_name == "vault_sample":
            # vault_sample hands back real note bodies directly (no separate
            # read_file follow-up) - the path is in its own output header
            # (`### Ground-Truth Sandboxed Vault Note (`path` - Exact
            # Content)`), not in args_dict, so extract it from what it
            # actually returned. vault_search deliberately isn't handled
            # here - it returns ranked snippets, not full bodies, so finding
            # a note via search doesn't mean its content was retrieved.
            read_paths.update(VAULT_PATH_TOKEN_RE.findall(tool_res))

    @classmethod
    def _content_unread(cls, text: str, read_paths: set[str]) -> str | None:
        """Returns the offending note name when `text` names a specific
        vault note whose content was never actually retrieved via a
        successful `read_file` call this run - the same "named it, never
        actually read it" fabrication shape `PersonaEngine._vault_ctx_title_
        missing` already catches on the primary persona path (that check
        compares a reply against the vault_ctx it was deterministically
        handed; this one compares a sub-agent's synthesis against its own
        tool-call history, since a sub-agent has no pre-fetched vault_ctx to
        check against). Only fires when NONE of the paths named in `text`
        were actually read (a synthesis correctly quoting one real note
        while merely mentioning another in passing isn't this case) and
        stays silent when `text` names no path at all - the same prose-only
        residual gap the primary check leaves open, for the same
        round-trip-frugal reason (no second model call to compare
        meaning)."""
        named = {p.rsplit("/", 1)[-1].lower() for p in VAULT_PATH_TOKEN_RE.findall(text)}
        named |= {m.lower() for m in cls._BARE_CITED_FILENAME_RE.findall(text)}
        if not named:
            return None
        read_names = {p.rsplit("/", 1)[-1].lower() for p in read_paths if p}
        if named & read_names:
            return None
        return sorted(named)[0]

    @staticmethod
    def _swap_in_unread_note(offending: str, task: "SubAgentTask") -> str:
        """Deterministic, zero-round-trip recovery for a synthesis flagged by
        `_content_unread`: reads the named note for real (plain file I/O, not
        another model call) via the same sandboxed lookup the rest of the
        vault layer uses, so the user gets the actual content instead of
        whatever the sub-agent invented for it. Falls back to an honest
        admission when the name doesn't resolve to a real, readable note -
        it was likely a plausible-sounding guess, not a genuine miss."""
        parent_prof = ProfileManager().get_profile(task.parent_agent)
        real = VaultManager.read_note(parent_prof, offending) if parent_prof else ""
        if real and not real.startswith("⚠️") and not real.startswith(
            "Error reading note"
        ) and "not found in allowed vault folders" not in real:
            return (
                f"That's not what I actually have — I never opened `{offending}` "
                f"this turn. Here's its real content:\n\n{real}"
            )
        return (
            f"I found a reference to `{offending}` but never actually opened it "
            "this turn, so I can't share its real content — ask me again and "
            "I'll read it properly."
        )

    # ------------------------------------------------------------------ #
    #  Public execution methods                                            #
    # ------------------------------------------------------------------ #

    @classmethod
    def execute_sub_agent_stream(cls, task: SubAgentTask) -> Generator[str, None, None]:
        """Streams the sub-agent execution, tool calling status, and final synthesized output."""
        (
            _,
            target_model,
            messages,
            active_clients,
            tool_to_client,
            all_litellm_tools,
            allowed_dirs,
            parent_prof,
        ) = cls._build_sub_agent_context(task)

        # Emit MCP connection warnings for stream consumers
        for s_name in list(task.mcp_servers) + [
            s
            for sk in task.skills
            if (sk_obj := skill_manager.get_skill(sk)) and sk_obj.mcp_servers
            for s in sk_obj.mcp_servers
        ]:
            if s_name not in active_clients and s_name not in (
                "shell",
                "git",
                "native",
            ):
                yield f"> ⚠️ Could not connect to MCP server `[{s_name}]`.\n"

        turn_count = 0
        final_synthesis = ""
        read_paths: set[str] = set()
        try:
            while turn_count < task.max_tool_turns:
                turn_count += 1
                last_turn = turn_count >= task.max_tool_turns
                kwargs: dict[str, Any] = {
                    "model": target_model,
                    "messages": messages
                    + (
                        [{"role": "user", "content": cls._LAST_TURN_NUDGE}]
                        if last_turn
                        else []
                    ),
                    "temperature": task.temperature,
                    "stream": False,
                }
                if all_litellm_tools and not last_turn:
                    kwargs["tools"] = all_litellm_tools
                    kwargs["tool_choice"] = "auto"
                cls._inject_api_key(kwargs, target_model)
                cls._inject_timeout(kwargs)

                response = litellm.completion(**kwargs)
                choice = response.choices[0]
                message = choice.message
                tool_calls = getattr(message, "tool_calls", None)

                if tool_calls and not last_turn:
                    messages.append(
                        message.to_dict()
                        if hasattr(message, "to_dict")
                        else dict(message)
                    )
                    for tc in tool_calls:
                        call_id, t_name, _, ok, tool_res, args_dict = (
                            cls._dispatch_tool_call(tc, tool_to_client, allowed_dirs, parent_prof)
                        )
                        cls._register_read(t_name, ok, args_dict, tool_res, read_paths)
                        yield f"> ⚙️ *Sub-agent calling tool:* `{t_name}`...\n"
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call_id,
                                "name": t_name,
                                "content": tool_res,
                            }
                        )
                    continue
                else:
                    final_synthesis = message.content or ""
                    break

            if not final_synthesis and turn_count >= task.max_tool_turns:
                final_synthesis = cls._forced_synthesis(
                    messages, target_model, task
                ) or (
                    "⚠️ Sub-agent hit its tool budget before finishing; retry with a narrower ask."
                )

            offending = cls._content_unread(final_synthesis, read_paths)
            if offending:
                final_synthesis = cls._swap_in_unread_note(offending, task)
            yield final_synthesis

        except Exception as e:
            yield f"\n⚠️ **Sub-Agent Execution Error ({target_model}):** {e}"

    @classmethod
    def execute_sub_agent_task(
        cls,
        task: SubAgentTask,
        on_progress: Callable[[str], None] | None = None,
    ) -> tuple[str, list[str]]:
        """Executes sub-agent task and returns (final_deliverable_text, tool_calls_summary_list).

        `on_progress`, if given, is called synchronously with each
        `tool(args)` string the instant that tool call completes — the same
        strings that end up in `tool_calls_summary_list`, just surfaced
        before the whole multi-turn loop finishes instead of only after.
        Purely a side-channel for a live terminal status; never awaited,
        never changes what gets returned."""
        (
            _,
            target_model,
            messages,
            active_clients,
            tool_to_client,
            all_litellm_tools,
            allowed_dirs,
            parent_prof,
        ) = cls._build_sub_agent_context(task)

        turn_count = 0
        final_synthesis = ""
        tool_calls_executed: list[str] = []
        read_paths: set[str] = set()

        try:
            while turn_count < task.max_tool_turns:
                turn_count += 1
                last_turn = turn_count >= task.max_tool_turns
                kwargs: dict[str, Any] = {
                    "model": target_model,
                    "messages": messages
                    + (
                        [{"role": "user", "content": cls._LAST_TURN_NUDGE}]
                        if last_turn
                        else []
                    ),
                    "temperature": task.temperature,
                    "stream": False,
                }
                if all_litellm_tools and not last_turn:
                    kwargs["tools"] = all_litellm_tools
                    kwargs["tool_choice"] = "auto"
                cls._inject_api_key(kwargs, target_model)
                cls._inject_timeout(kwargs)

                response = litellm.completion(**kwargs)
                choice = response.choices[0]
                message = choice.message
                tool_calls = getattr(message, "tool_calls", None)

                if tool_calls and not last_turn:
                    messages.append(
                        message.to_dict()
                        if hasattr(message, "to_dict")
                        else dict(message)
                    )
                    for tc in tool_calls:
                        call_id, t_name, arg_summary, ok, tool_res, args_dict = (
                            cls._dispatch_tool_call(tc, tool_to_client, allowed_dirs, parent_prof)
                        )
                        cls._register_read(t_name, ok, args_dict, tool_res, read_paths)
                        call_summary = (
                            f"{t_name}({arg_summary})" if arg_summary else f"{t_name}()"
                        )
                        tool_calls_executed.append(call_summary)
                        if on_progress:
                            try:
                                on_progress(call_summary)
                            except Exception:
                                log.debug(
                                    "on_progress callback failed, ignoring",
                                    exc_info=True,
                                )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call_id,
                                "name": t_name,
                                "content": tool_res,
                            }
                        )
                    continue
                else:
                    final_synthesis = message.content or ""
                    break

            if not final_synthesis and turn_count >= task.max_tool_turns:
                final_synthesis = cls._forced_synthesis(
                    messages, target_model, task
                ) or (
                    "⚠️ Sub-agent hit its tool budget before finishing; retry with a narrower ask."
                )

            offending = cls._content_unread(final_synthesis, read_paths)
            if offending:
                final_synthesis = cls._swap_in_unread_note(offending, task)

            return final_synthesis, tool_calls_executed
        except Exception as e:
            return (
                f"⚠️ **Sub-Agent Execution Error ({target_model}):** {e}",
                tool_calls_executed,
            )


# Singleton sub-agent engine
sub_agent_engine = SubAgentEngine()
