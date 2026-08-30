"""
Ephemeral Sub-Agent Worker Engine & Multi-Turn Tool Execution Loop for Sympose.
Executes isolated worker tasks loaded with specific skills and MCP servers without polluting main agent context.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Generator, Tuple
import litellm

from sympose.config import config_manager, DEFAULT_WORKER_MODEL
from sympose.skills import skill_manager
from sympose.mcp import mcp_registry, MCPClient
from sympose.native_tools import NativeTools
from sympose.profiles import ProfileManager
from sympose.vault import VaultManager

log = logging.getLogger(__name__)

MAX_TOOL_OUTPUT_CHARS = 20000


class WorkerTask:
    """Specification for an isolated, ephemeral worker execution."""

    def __init__(
        self,
        task_prompt: str,
        skills: Optional[List[str]] = None,
        mcp_servers: Optional[List[str]] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tool_turns: Optional[int] = None,
        parent_agent: str = "orchestrator",
    ):
        self.task_prompt = task_prompt.strip()
        self.skills = skills or []
        self.mcp_servers = mcp_servers or []
        self.model = model
        self.temperature = temperature
        default_turns = int(config_manager.get("performance.max_worker_tool_turns", 8))
        self.max_tool_turns = max_tool_turns if max_tool_turns is not None else default_turns
        self.parent_agent = parent_agent


class WorkerEngine:
    """Executes single/multi-turn worker runs with tool calling and skill playbooks."""

    # ------------------------------------------------------------------ #
    #  Shared setup helpers                                                #
    # ------------------------------------------------------------------ #

    @classmethod
    def _build_worker_context(cls, task: WorkerTask) -> Tuple[
        str,           # system_prompt
        str,           # target_model
        List[Dict[str, Any]],   # initial messages
        Dict[str, MCPClient],   # active_clients
        Dict[str, MCPClient],   # tool_to_client
        List[Dict[str, Any]],   # all_litellm_tools
        Optional[List[str]],    # allowed_dirs
    ]:
        """Builds the shared execution context for both streaming and non-streaming workers."""
        skills_text = skill_manager.format_skills_for_prompt(task.skills)

        # Resolve parent agent sandbox whitelist
        parent_prof = ProfileManager().get_profile(task.parent_agent)
        allowed_dirs = VaultManager.get_allowed_dirs(parent_prof) if parent_prof else None

        # Resolve MCP Clients & Tools + Native Built-in Tools
        active_clients: Dict[str, MCPClient] = {}
        tool_to_client: Dict[str, MCPClient] = {}
        all_litellm_tools: List[Dict[str, Any]] = list(NativeTools.NATIVE_SCHEMAS)

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
                log.debug("WorkerEngine: could not connect to MCP server [%s]", server_name)

        # Load system prompt template
        mv = os.getenv("MASTER_VAULT_PATH")
        env_lines = [f"- Workspace Directory: `{os.getcwd()}`"] + ([f"- Obsidian Vault Directory: `{mv}`"] if mv else [])
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tmpl = ""
        for tp in (os.path.join(repo_root, "prompts", "worker_system.md"), os.path.join("prompts", "worker_system.md")):
            if os.path.exists(tp):
                try:
                    with open(tp, "r", encoding="utf-8") as f:
                        tmpl = f.read().strip()
                        break
                except Exception as exc:
                    log.debug("WorkerEngine: failed to read template %s: %s", tp, exc)

        if not tmpl:
            tmpl = (
                "You are an ephemeral Sub-Agent Worker in Sympose on macOS dispatched by parent agent @{{parent_agent}}.\n\n"
                "### RUNTIME ENVIRONMENT:\n{{environment}}\n\n"
                "### UNIVERSAL OPERATIONAL DIRECTIVES:\n"
                "1. GROUND-TRUTH EXECUTION: Use tools directly.\n"
                "2. ZERO HAND-WAVING: Output factual deliverables.\n"
                "3. RAPID COMPLETION."
            )

        system_prompt = tmpl.replace("{{parent_agent}}", task.parent_agent).replace("{{environment}}", "\n".join(env_lines))
        if skills_text:
            system_prompt += f"\n\n{skills_text}"

        # Resolve model: task override → skill recommendation → env default
        target_model = task.model
        if not target_model:
            for s_name in task.skills:
                s_obj = skill_manager.get_skill(s_name)
                if s_obj and s_obj.recommended_models:
                    target_model = s_obj.recommended_models[0]
                    break
        target_model = target_model or DEFAULT_WORKER_MODEL

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task.task_prompt},
        ]

        return system_prompt, target_model, messages, active_clients, tool_to_client, all_litellm_tools, allowed_dirs

    @staticmethod
    def _inject_api_key(kwargs: Dict[str, Any], target_model: str) -> None:
        """Injects the correct API key into litellm kwargs based on model provider prefix."""
        for pfx, key in (
            ("gemini/", "GEMINI_API_KEY"),
            ("anthropic/", "ANTHROPIC_API_KEY"),
            ("openai/", "OPENAI_API_KEY"),
            ("openrouter/", "OPENROUTER_API_KEY"),
        ):
            if target_model.startswith(pfx) and os.getenv(key):
                kwargs["api_key"] = os.getenv(key)
                return

    @staticmethod
    def _dispatch_tool_call(
        tc: Any,
        tool_to_client: Dict[str, MCPClient],
        allowed_dirs: Optional[List[str]],
    ) -> Tuple[str, str, str, bool, str]:
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

        arg_summary = ", ".join(f"{k}={v}" for k, v in args_dict.items() if k in ("path", "query", "command", "file_path"))

        if t_name in ("run_command", "read_file", "web_search"):
            ok, tool_res = NativeTools.execute(t_name, args_dict, allowed_dirs=allowed_dirs)
        else:
            client = tool_to_client.get(t_name)
            if client:
                ok, tool_res = client.call_tool(t_name, args_dict)
            else:
                ok, tool_res = False, f"Tool `{t_name}` not registered with active MCP servers."

        if len(tool_res) > MAX_TOOL_OUTPUT_CHARS:
            tool_res = tool_res[:MAX_TOOL_OUTPUT_CHARS] + "\n...[Output truncated for brevity]..."

        return call_id, t_name, arg_summary, ok, tool_res

    # ------------------------------------------------------------------ #
    #  Public execution methods                                            #
    # ------------------------------------------------------------------ #

    @classmethod
    def execute_worker_stream(cls, task: WorkerTask) -> Generator[str, None, None]:
        """Streams the worker execution, tool calling status, and final synthesized output."""
        _, target_model, messages, active_clients, tool_to_client, all_litellm_tools, allowed_dirs = cls._build_worker_context(task)

        # Emit MCP connection warnings for stream consumers
        for s_name in list(task.mcp_servers) + [s for sk in task.skills if (sk_obj := skill_manager.get_skill(sk)) and sk_obj.mcp_servers for s in sk_obj.mcp_servers]:
            if s_name not in active_clients and s_name not in ("shell", "git", "native"):
                yield f"> ⚠️ Could not connect to MCP server `[{s_name}]`.\n"

        turn_count = 0
        final_synthesis = ""
        try:
            while turn_count < task.max_tool_turns:
                turn_count += 1
                kwargs: Dict[str, Any] = {
                    "model": target_model,
                    "messages": messages,
                    "temperature": task.temperature,
                    "stream": False,
                }
                if all_litellm_tools:
                    kwargs["tools"] = all_litellm_tools
                    kwargs["tool_choice"] = "auto"
                cls._inject_api_key(kwargs, target_model)

                response = litellm.completion(**kwargs)
                choice = response.choices[0]
                message = choice.message
                tool_calls = getattr(message, "tool_calls", None)

                if tool_calls:
                    messages.append(message.to_dict() if hasattr(message, "to_dict") else dict(message))
                    for tc in tool_calls:
                        call_id, t_name, _, ok, tool_res = cls._dispatch_tool_call(tc, tool_to_client, allowed_dirs)
                        yield f"> ⚙️ *Worker calling tool:* `{t_name}`...\n"
                        messages.append({"role": "tool", "tool_call_id": call_id, "name": t_name, "content": tool_res})
                    continue
                else:
                    final_synthesis = message.content or ""
                    break

            if not final_synthesis and turn_count >= task.max_tool_turns:
                final_synthesis = "⚠️ Worker reached maximum tool turns without completing final synthesis."
            yield final_synthesis

        except Exception as e:
            yield f"\n⚠️ **Worker Execution Error ({target_model}):** {e}"

    @classmethod
    def execute_worker_task(cls, task: WorkerTask) -> Tuple[str, List[str]]:
        """Executes worker task and returns (final_deliverable_text, tool_calls_summary_list)."""
        _, target_model, messages, active_clients, tool_to_client, all_litellm_tools, allowed_dirs = cls._build_worker_context(task)

        turn_count = 0
        final_synthesis = ""
        tool_calls_executed: List[str] = []

        try:
            while turn_count < task.max_tool_turns:
                turn_count += 1
                kwargs: Dict[str, Any] = {
                    "model": target_model,
                    "messages": messages,
                    "temperature": task.temperature,
                    "stream": False,
                }
                if all_litellm_tools:
                    kwargs["tools"] = all_litellm_tools
                    kwargs["tool_choice"] = "auto"
                cls._inject_api_key(kwargs, target_model)

                response = litellm.completion(**kwargs)
                choice = response.choices[0]
                message = choice.message
                tool_calls = getattr(message, "tool_calls", None)

                if tool_calls:
                    messages.append(message.to_dict() if hasattr(message, "to_dict") else dict(message))
                    for tc in tool_calls:
                        call_id, t_name, arg_summary, ok, tool_res = cls._dispatch_tool_call(tc, tool_to_client, allowed_dirs)
                        tool_calls_executed.append(f"{t_name}({arg_summary})" if arg_summary else f"{t_name}()")
                        messages.append({"role": "tool", "tool_call_id": call_id, "name": t_name, "content": tool_res})
                    continue
                else:
                    final_synthesis = message.content or ""
                    break

            if not final_synthesis and turn_count >= task.max_tool_turns:
                final_synthesis = "⚠️ Worker reached maximum tool turns without completing final synthesis."

            return final_synthesis, tool_calls_executed
        except Exception as e:
            return f"⚠️ **Worker Execution Error ({target_model}):** {e}", tool_calls_executed


# Singleton worker engine
worker_engine = WorkerEngine()
