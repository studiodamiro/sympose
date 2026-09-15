"""
Ephemeral Sub-Agent Engine & Multi-Turn Tool Execution Loop for Sympose.
Executes isolated sub-agent tasks loaded with specific skills and MCP servers without polluting main persona context.
"""

import json
import logging
import os
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
from sympose.vault import VaultManager

log = logging.getLogger(__name__)

MAX_TOOL_OUTPUT_CHARS = 20000


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
    ]:
        """Builds the shared execution context for both streaming and non-streaming sub-agents."""
        skills_text = skill_manager.format_skills_for_prompt(task.skills)

        # Resolve parent agent sandbox whitelist
        parent_prof = ProfileManager().get_profile(task.parent_agent)
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
        if any(s in ("vault_recall", "vault_write") for s in task.skills):
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
        )

    @staticmethod
    def _inject_api_key(kwargs: dict[str, Any], target_model: str) -> None:
        """Injects the correct API key into litellm kwargs based on model provider prefix."""
        api_key = resolve_api_key(target_model)
        if api_key:
            kwargs["api_key"] = api_key

    @staticmethod
    def _dispatch_tool_call(
        tc: Any,
        tool_to_client: dict[str, MCPClient],
        allowed_dirs: list[str] | None,
    ) -> tuple[str, str, str, bool, str]:
        """Parses a tool_call object and executes it. Returns (call_id, t_name, arg_summary, ok, tool_res)."""
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
            if k in ("path", "query", "command", "file_path")
        )

        if t_name in ("run_command", "read_file", "web_search"):
            ok, tool_res = NativeTools.execute(
                t_name, args_dict, allowed_dirs=allowed_dirs
            )
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

        return call_id, t_name, arg_summary, ok, tool_res

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
            return (
                litellm.completion(**kwargs).choices[0].message.content or ""
            ).strip()
        except Exception:
            return ""

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
                        call_id, t_name, _, ok, tool_res = cls._dispatch_tool_call(
                            tc, tool_to_client, allowed_dirs
                        )
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
        ) = cls._build_sub_agent_context(task)

        turn_count = 0
        final_synthesis = ""
        tool_calls_executed: list[str] = []

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
                        call_id, t_name, arg_summary, ok, tool_res = (
                            cls._dispatch_tool_call(tc, tool_to_client, allowed_dirs)
                        )
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

            return final_synthesis, tool_calls_executed
        except Exception as e:
            return (
                f"⚠️ **Sub-Agent Execution Error ({target_model}):** {e}",
                tool_calls_executed,
            )


# Singleton sub-agent engine
sub_agent_engine = SubAgentEngine()
