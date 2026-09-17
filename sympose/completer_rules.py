"""
Per-command Tab-completion routing for the Sympose CLI. `command_completions`
used to be one `if cmd == ...` ladder for every slash command's
sub-arguments — mccabe flagged it at complexity 34. Restructured the same
way as the other worst-offender command dispatchers this pass
(`commands.py`'s `intercept`): each command's completion logic is now its
own `_complete_*` function, dispatched through `_COMMAND_COMPLETERS` keyed
by command word, so `command_completions` itself is just a lookup plus the
one fallback case (an inline `@mention`) that doesn't have its own command
word. The root-command list and the dynamic candidate lookups (personas,
skills, sessions, model catalog) stay on `SymposeCompleter`, which
delegates here once a command word plus a space has been typed.
"""

import logging
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

from sympose.models import ModelCatalog


def _complete_history(comp: Any, tokens: list[str], line_l: str, text: str) -> list[str]:
    """/history, /sessions -> subcommands, session ids"""
    history_subcmds = ["list", "all", "new", "resume", "view", "delete"]
    if len(tokens) == 1 or (len(tokens) == 2 and not line_l.endswith(" ")):
        return [opt for opt in history_subcmds if opt.startswith(text)]
    sub = tokens[1].lower() if len(tokens) > 1 else ""
    if sub in ("resume", "load", "view", "show", "delete", "remove", "rm"):
        if len(tokens) == 2 or (len(tokens) == 3 and not line_l.endswith(" ")):
            s_ids = comp.get_session_ids()
            return [s for s in s_ids if s.startswith(text)]
    return []


def _complete_persona_handle_arg(
    comp: Any, tokens: list[str], line_l: str, text: str
) -> list[str]:
    """/switch, /delete, /retire, /ask -> @persona handles"""
    personas = comp.get_personas()
    return [p for p in personas if p.startswith(text) or p.lstrip("@").startswith(text)]


def _complete_subagent(comp: Any, tokens: list[str], line_l: str, text: str) -> list[str]:
    """/subagent -> skills and mcp servers"""
    if len(tokens) == 1 or (len(tokens) == 2 and not line_l.endswith(" ")):
        targets = comp.get_sub_agent_targets()
        return [t for t in targets if t.startswith(text)]
    return []


def _complete_skill_persona_arg(comp: Any, text: str) -> list[str]:
    return [
        p for p in comp.get_personas() if p.startswith(text) or p.lstrip("@").startswith(text)
    ]


def _complete_skill(comp: Any, tokens: list[str], line_l: str, text: str) -> list[str]:
    """/skill, /skills, /tools -> subcommands, skill names, and @personas"""
    skill_subcmds = ["list", "add", "remove", "show"]
    all_skills = comp.get_skills()

    # Subcommand completion: "/skill " or "/skill a"
    if len(tokens) == 1 or (len(tokens) == 2 and not line_l.endswith(" ")):
        options = skill_subcmds + all_skills
        return [opt for opt in options if opt.startswith(text)]

    sub = tokens[1].lower() if len(tokens) > 1 else ""
    mutating_subs = ("add", "mount", "install", "remove", "unmount", "uninstall", "rm")

    # Skill name completion: "/skill add ", "/skill show ", "/skill remove "
    if sub in (*mutating_subs, "show", "view", "info"):
        if len(tokens) == 2 or (len(tokens) == 3 and not line_l.endswith(" ")):
            return [s for s in all_skills if s.startswith(text)]
        # Persona handle completion: "/skill add git_workflow @"
        if len(tokens) >= 3 and sub in mutating_subs:
            return _complete_skill_persona_arg(comp, text)
    return []


def _complete_vault(comp: Any, tokens: list[str], line_l: str, text: str) -> list[str]:
    """/vault -> back, list, backlinks, open, read"""
    vault_subcmds = ["back", "list", "backlinks", "open", "read"]
    if len(tokens) == 1 or (len(tokens) == 2 and not line_l.endswith(" ")):
        return [opt for opt in vault_subcmds if opt.startswith(text)]
    return []


def _complete_save(comp: Any, tokens: list[str], line_l: str, text: str) -> list[str]:
    """/save -> both, memory, obsidian"""
    return [opt for opt in comp.SAVE_OPTIONS if opt.startswith(text)]


def _complete_render(comp: Any, tokens: list[str], line_l: str, text: str) -> list[str]:
    """/render -> hybrid, buffered, raw"""
    render_subcmds = ["hybrid", "buffered", "raw"]
    if len(tokens) == 1 or (len(tokens) == 2 and not line_l.endswith(" ")):
        return [opt for opt in render_subcmds if opt.startswith(text)]
    return []


def _complete_help(comp: Any, tokens: list[str], line_l: str, text: str) -> list[str]:
    """/help -> available commands"""
    help_topics = [c.lstrip("/") for c in comp.ROOT_COMMANDS if c.startswith("/")] + [
        c for c in comp.ROOT_COMMANDS if c.startswith("/")
    ]
    return [t for t in help_topics if t.startswith(text)]


def _complete_config(comp: Any, tokens: list[str], line_l: str, text: str) -> list[str]:
    """/config -> get|set subcommand, then a config key (also leniently
    completes a bare key prefix: "/config vau" -> vault.* keys)"""
    subs = ("get", "set")
    on_first = len(tokens) == 1 or (len(tokens) == 2 and not line_l.endswith(" "))
    if on_first:
        return [o for o in (list(subs) + comp.CONFIG_KEYS) if o.startswith(text)]
    sub = tokens[1].lower()
    on_key = (len(tokens) == 2 and line_l.endswith(" ")) or (
        len(tokens) == 3 and not line_l.endswith(" ")
    )
    if sub in subs and on_key:
        return [k for k in comp.CONFIG_KEYS if k.startswith(text)]
    return []


def _complete_persona(comp: Any, tokens: list[str], line_l: str, text: str) -> list[str]:
    """/persona -> show|set, then @handle, then persona keys"""
    if len(tokens) < 2 or (len(tokens) == 2 and not line_l.endswith(" ")):
        return [s for s in ("show", "set") if s.startswith(text)]
    if text.startswith("@") or (
        len(tokens) >= 2 and tokens[-1] in ("show", "set") and line_l.endswith(" ")
    ):
        return [p for p in comp.get_personas() if p.startswith(text)]
    if "set" in tokens:
        return [k for k in comp.PERSONA_KEYS if k.startswith(text)]
    return []


def _complete_compact(comp: Any, tokens: list[str], line_l: str, text: str) -> list[str]:
    """/compact -> shared, @personas"""
    compact_targets = ["shared"] + comp.get_personas()
    return [
        t
        for t in compact_targets
        if t.startswith(text) or t.lstrip("@").startswith(text)
    ]


def _complete_model_find(text: str) -> list[str]:
    common_terms = [
        "sonnet",
        "deepseek",
        "flash",
        "qwen",
        "llama",
        "haiku",
        "opus",
        "gpt",
    ]
    return [t for t in common_terms if t.startswith(text)]


def _complete_model(comp: Any, tokens: list[str], line_l: str, text: str) -> list[str]:
    """/model -> model presets, actions, and dynamic candidates"""
    if len(tokens) >= 2 and tokens[1].lower() == "find":
        return _complete_model_find(text)

    candidates = list(comp.COMMON_MODELS)
    if text.startswith("openrouter/") or (
        len(tokens) >= 2 and tokens[1].startswith("openrouter/")
    ):
        try:
            dyn = ModelCatalog.get_completion_candidates(text)
            for d in dyn:
                if d not in candidates:
                    candidates.append(d)
        except Exception as e:
            log.debug("Dynamic model-catalog completion failed: %s", e)
    return [m for m in candidates if m.startswith(text)]


_COMMAND_COMPLETERS: dict[str, Callable[[Any, list[str], str, str], list[str]]] = {
    "/history": _complete_history,
    "/sessions": _complete_history,
    "/switch": _complete_persona_handle_arg,
    "/delete": _complete_persona_handle_arg,
    "/retire": _complete_persona_handle_arg,
    "/ask": _complete_persona_handle_arg,
    "/subagent": _complete_subagent,
    "/skill": _complete_skill,
    "/skills": _complete_skill,
    "/tools": _complete_skill,
    "/vault": _complete_vault,
    "/save": _complete_save,
    "/render": _complete_render,
    "/help": _complete_help,
    "/config": _complete_config,
    "/persona": _complete_persona,
    "/compact": _complete_compact,
    "/model": _complete_model,
}


def command_completions(comp: Any, line_l: str, text: str) -> list[str]:
    """Candidates for the active word once `line_l` carries a command and an
    argument position. `comp` is the `SymposeCompleter` — used for its dynamic
    lookups (`get_personas`, `get_skills`, ...) and schema-derived key lists."""
    tokens = line_l.split()
    cmd = tokens[0].lower()

    handler = _COMMAND_COMPLETERS.get(cmd)
    if handler:
        return handler(comp, tokens, line_l, text)

    # Inline @mention completion
    if text.startswith("@"):
        return [p for p in comp.get_personas() if p.startswith(text)]

    return []
