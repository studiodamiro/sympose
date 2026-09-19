"""
SPAWN_SUB_AGENT tag handler for `ActionProcessor` (ADR-137, split out of
actions.py).
"""

from typing import TYPE_CHECKING

from sympose.mcp import mcp_registry
from sympose.skills import skill_manager
from sympose.sub_agents import SubAgentEngine, SubAgentTask

if TYPE_CHECKING:
    from sympose.actions_context import _ActionContext


class SubAgentActionMixin:
    @staticmethod
    def _resolve_sub_agent_loadout(spec: str) -> tuple[list[str], list[str]]:
        """Splits a SPAWN_SUB_AGENT tag's comma/semicolon-separated spec into
        (skills_to_load, mcp_to_load) — an unrecognized token is treated as a
        skill name anyway, so a not-yet-indexed skill still shows up in the
        badge rather than silently vanishing."""
        tokens = [t.strip() for t in spec.replace(";", ",").split(",") if t.strip()]
        skills_to_load = [tok for tok in tokens if skill_manager.get_skill(tok)]
        mcp_to_load = [tok for tok in tokens if tok.lower() in mcp_registry.servers]
        for tok in tokens:
            if tok not in skills_to_load and tok not in mcp_to_load:
                skills_to_load.append(tok)
        return skills_to_load, mcp_to_load

    @staticmethod
    def _append_user_constraint(task_prompt: str, user_prompt: str) -> str:
        """Appends the user's own words verbatim when the sub-agent's
        paraphrased task_prompt seems to have dropped them. The tag's task
        string is a paraphrase written by whichever model is driving this
        turn - a weak one can lose a constraint the user actually stated
        (live bug: "give me a random note from the Daily folder" got
        shortened to a bare "Roulette" task, and the sub-agent searched the
        whole vault instead). Appending the user's own words, verbatim and
        mechanical rather than re-paraphrased, means the constraint survives
        regardless of which model authored the tag."""
        original_ask = user_prompt.strip()
        if original_ask and original_ask.lower() not in task_prompt.lower():
            return (
                f"{task_prompt}\n\n"
                f'(The user\'s own words this turn, in case the task above '
                f'dropped a constraint: "{original_ask}")'
            )
        return task_prompt

    @staticmethod
    def _build_sub_agent_report(
        badge_spec: str,
        task_prompt: str,
        tool_calls_executed: list[str],
        clean_sub_agent_res: str,
    ) -> str:
        report_md = [
            f"> ### 🛠️ Sub-Agent Report `[{badge_spec}]`",
            f"> **Task:** *{task_prompt}*",
            "> ",
            "> ---",
            "> ",
        ]
        if tool_calls_executed:
            tool_str = "  •  ".join([f"⚙️ `{tc}`" for tc in tool_calls_executed])
            report_md.append(f"> {tool_str}")
            report_md.append("> ")
        for line in clean_sub_agent_res.strip().splitlines():
            report_md.append(f"> {line}")
        return "\n" + "\n".join(report_md)

    # --- 5. SPAWN_SUB_AGENT -----------------------------------------------------
    @classmethod
    def _handle_spawn_sub_agent(cls, ctx: "_ActionContext", inner: str) -> str:
        parts = inner.split("|", 1)
        spec, task_prompt = parts[0].strip(), parts[1].strip()
        if not task_prompt:
            return ""

        skills_to_load, mcp_to_load = cls._resolve_sub_agent_loadout(spec)
        task_prompt = cls._append_user_constraint(task_prompt, ctx.user_prompt)

        task = SubAgentTask(
            task_prompt=task_prompt,
            skills=skills_to_load,
            mcp_servers=mcp_to_load,
            parent_agent=ctx.handle,
        )
        final_synthesis, tool_calls_executed = SubAgentEngine.execute_sub_agent_task(
            task, on_progress=ctx.on_progress
        )
        if ctx.depth < cls.MAX_ACTION_DEPTH:
            clean_sub_agent_res, sub_agent_sub_badges = cls.execute_actions(
                ctx.profile_manager,
                "sub_agent",
                final_synthesis,
                user_prompt=task_prompt,
                depth=ctx.depth + 1,
                on_progress=ctx.on_progress,
                on_action=ctx.on_action,
            )
        else:
            clean_sub_agent_res, sub_agent_sub_badges = (
                cls.strip_action_tags(final_synthesis),
                [],
            )
        for wb in sub_agent_sub_badges:
            if wb not in ctx.badges:
                ctx.badges.append(wb)

        badge_spec = (
            f"Skills: `{', '.join(skills_to_load)}`"
            if skills_to_load
            else (
                f"MCP: `{', '.join(mcp_to_load)}`" if mcp_to_load else "General Sandbox"
            )
        )
        ctx.badges.append(
            cls._build_sub_agent_report(
                badge_spec, task_prompt, tool_calls_executed, clean_sub_agent_res
            )
        )
        ctx.fire_action("SPAWN_SUB_AGENT", badge_spec)
        return ""
