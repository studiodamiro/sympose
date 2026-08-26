"""
Ephemeral Sub-Agent Worker Engine & Multi-Turn Tool Execution Loop for Sympose.
Executes isolated worker tasks loaded with specific skills and MCP servers without polluting main agent context.
"""

import os
import json
from typing import Dict, List, Any, Optional, Generator
import litellm

from sympose.config import config_manager
from sympose.skills import skill_manager
from sympose.mcp import mcp_registry, MCPClient
from sympose.native_tools import NativeTools
from sympose.profiles import ProfileManager
from sympose.vault import VaultManager

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

    @classmethod
    def execute_worker_stream(cls, task: WorkerTask) -> Generator[str, None, None]:
        """Streams the worker execution, tool calling status, and final synthesized output."""
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
                yield f"> ⚠️ Could not connect to MCP server `[{server_name}]`.\n"

        mv = os.getenv("MASTER_VAULT_PATH")
        env_lines = [f"- Workspace Directory: `{os.getcwd()}`"] + ([f"- Obsidian Vault Directory: `{mv}`"] if mv else [])
        tmpl_path = os.path.join("prompts", "worker_system.md")
        tmpl = ""
        if os.path.exists(tmpl_path):
            try:
                with open(tmpl_path, "r", encoding="utf-8") as f: tmpl = f.read().strip()
            except Exception: pass
        if not tmpl: tmpl = "You are an ephemeral Sub-Agent Worker in Sympose on macOS dispatched by parent agent @{{parent_agent}}.\n\n### RUNTIME ENVIRONMENT:\n{{environment}}\n\n### UNIVERSAL OPERATIONAL DIRECTIVES:\n1. GROUND-TRUTH EXECUTION: Use tools directly.\n2. ZERO HAND-WAVING: Output factual deliverables.\n3. RAPID COMPLETION."

        system_prompt = tmpl.replace("{{parent_agent}}", task.parent_agent).replace("{{environment}}", "\n".join(env_lines))
        if skills_text: system_prompt += f"\n\n{skills_text}"
        target_model = task.model
        if not target_model:
            for s_name in task.skills:
                s_obj = skill_manager.get_skill(s_name)
                if s_obj and s_obj.recommended_models:
                    target_model = s_obj.recommended_models[0]
                    break
        target_model = target_model or os.getenv("DEFAULT_MODEL", "gemini/gemini-3.5-flash-lite")

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task.task_prompt},
        ]

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

                if target_model.startswith("gemini/") and os.getenv("GEMINI_API_KEY"):
                    kwargs["api_key"] = os.getenv("GEMINI_API_KEY")
                elif target_model.startswith("anthropic/") and os.getenv("ANTHROPIC_API_KEY"):
                    kwargs["api_key"] = os.getenv("ANTHROPIC_API_KEY")
                elif target_model.startswith("openai/") and os.getenv("OPENAI_API_KEY"):
                    kwargs["api_key"] = os.getenv("OPENAI_API_KEY")
                elif target_model.startswith("openrouter/") and os.getenv("OPENROUTER_API_KEY"):
                    kwargs["api_key"] = os.getenv("OPENROUTER_API_KEY")

                response = litellm.completion(**kwargs)
                choice = response.choices[0]
                message = choice.message
                tool_calls = getattr(message, "tool_calls", None)

                if tool_calls:
                    messages.append(message.to_dict() if hasattr(message, "to_dict") else dict(message))

                    for tc in tool_calls:
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

                        yield f"> ⚙️ *Worker calling tool:* `{t_name}`...\n"

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

                        messages.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "name": t_name,
                            "content": tool_res,
                        })
                    continue
                else:
                    final_synthesis = message.content or ""
                    break

            if not final_synthesis and turn_count >= task.max_tool_turns:
                final_synthesis = "⚠️ Worker reached maximum tool turns without completing final synthesis."

            yield final_synthesis

        except Exception as e:
            err_str = str(e)
            yield f"\n⚠️ **Worker Execution Error ({target_model}):** {err_str}"


# Singleton worker engine
worker_engine = WorkerEngine()
