"""
Per-command Tab-completion routing for the Sympose CLI. `command_completions`
holds the `if cmd == ...` ladder for every slash command's sub-arguments; the
root-command list and the dynamic candidate lookups (personas, skills, sessions,
model catalog) stay on `SymposeCompleter`, which delegates here once a command
word plus a space has been typed.
"""

from typing import Any, List

from sympose.models import ModelCatalog


def command_completions(comp: Any, line_l: str, text: str) -> List[str]:
    """Candidates for the active word once `line_l` carries a command and an
    argument position. `comp` is the `SymposeCompleter` — used for its dynamic
    lookups (`get_personas`, `get_skills`, ...) and schema-derived key lists."""
    tokens = line_l.split()
    cmd = tokens[0].lower()

    # /history, /sessions -> subcommands, session ids
    if cmd in ("/history", "/sessions"):
        history_subcmds = ["list", "all", "new", "resume", "view", "delete"]
        if len(tokens) == 1 or (len(tokens) == 2 and not line_l.endswith(" ")):
            return [opt for opt in history_subcmds if opt.startswith(text)]
        sub = tokens[1].lower() if len(tokens) > 1 else ""
        if sub in ("resume", "load", "view", "show", "delete", "remove", "rm"):
            if len(tokens) == 2 or (len(tokens) == 3 and not line_l.endswith(" ")):
                s_ids = comp.get_session_ids()
                return [s for s in s_ids if s.startswith(text)]

    # /switch, /delete, /retire, /ask -> @persona handles
    if cmd in ("/switch", "/delete", "/retire", "/ask"):
        personas = comp.get_personas()
        return [p for p in personas if p.startswith(text) or p.lstrip("@").startswith(text)]

    # /worker -> skills and mcp servers
    if cmd == "/worker":
        if len(tokens) == 1 or (len(tokens) == 2 and not line_l.endswith(" ")):
            targets = comp.get_worker_targets()
            return [t for t in targets if t.startswith(text)]

    # /skill, /skills, /tools -> subcommands, skill names, and @personas
    if cmd in ("/skill", "/skills", "/tools"):
        skill_subcmds = ["list", "add", "remove", "show"]
        all_skills = comp.get_skills()

        # Subcommand completion: "/skill " or "/skill a"
        if len(tokens) == 1 or (len(tokens) == 2 and not line_l.endswith(" ")):
            options = skill_subcmds + all_skills
            return [opt for opt in options if opt.startswith(text)]

        sub = tokens[1].lower() if len(tokens) > 1 else ""

        # Skill name completion: "/skill add ", "/skill show ", "/skill remove "
        if sub in ("add", "mount", "install", "show", "view", "info", "remove", "unmount", "uninstall", "rm"):
            if len(tokens) == 2 or (len(tokens) == 3 and not line_l.endswith(" ")):
                return [s for s in all_skills if s.startswith(text)]
            # Persona handle completion: "/skill add git_workflow @"
            if len(tokens) >= 3 and sub in ("add", "mount", "install", "remove", "unmount", "uninstall", "rm"):
                return [p for p in comp.get_personas() if p.startswith(text) or p.lstrip("@").startswith(text)]

    # /vault -> back, list, backlinks, open, read
    if cmd == "/vault":
        vault_subcmds = ["back", "list", "backlinks", "open", "read"]
        if len(tokens) == 1 or (len(tokens) == 2 and not line_l.endswith(" ")):
            return [opt for opt in vault_subcmds if opt.startswith(text)]

    # /save -> both, memory, obsidian
    if cmd == "/save":
        return [opt for opt in comp.SAVE_OPTIONS if opt.startswith(text)]

    # /render -> hybrid, buffered, raw
    if cmd == "/render":
        render_subcmds = ["hybrid", "buffered", "raw"]
        if len(tokens) == 1 or (len(tokens) == 2 and not line_l.endswith(" ")):
            return [opt for opt in render_subcmds if opt.startswith(text)]

    # /help -> available commands
    if cmd == "/help":
        help_topics = [c.lstrip("/") for c in comp.ROOT_COMMANDS if c.startswith("/")] + [c for c in comp.ROOT_COMMANDS if c.startswith("/")]
        return [t for t in help_topics if t.startswith(text)]

    # /config -> get|set subcommand, then a config key (also leniently
    # completes a bare key prefix: "/config vau" -> vault.* keys)
    if cmd == "/config":
        subs = ("get", "set")
        on_first = len(tokens) == 1 or (len(tokens) == 2 and not line_l.endswith(" "))
        if on_first:
            return [o for o in (list(subs) + comp.CONFIG_KEYS) if o.startswith(text)]
        sub = tokens[1].lower()
        on_key = (len(tokens) == 2 and line_l.endswith(" ")) or (len(tokens) == 3 and not line_l.endswith(" "))
        if sub in subs and on_key:
            return [k for k in comp.CONFIG_KEYS if k.startswith(text)]
        return []

    # /persona -> show|set, then @handle, then persona keys
    if cmd == "/persona":
        if len(tokens) < 2 or (len(tokens) == 2 and not line_l.endswith(" ")):
            return [s for s in ("show", "set") if s.startswith(text)]
        if text.startswith("@") or (len(tokens) >= 2 and tokens[-1] in ("show", "set") and line_l.endswith(" ")):
            return [p for p in comp.get_personas() if p.startswith(text)]
        if "set" in tokens:
            return [k for k in comp.PERSONA_KEYS if k.startswith(text)]

    # /compact -> shared, @personas
    if cmd == "/compact":
        compact_targets = ["shared"] + comp.get_personas()
        return [t for t in compact_targets if t.startswith(text) or t.lstrip("@").startswith(text)]

    # /model -> model presets, actions, and dynamic candidates
    if cmd == "/model":
        if len(tokens) >= 2 and tokens[1].lower() == "find":
            common_terms = ["sonnet", "deepseek", "flash", "qwen", "llama", "haiku", "opus", "gpt"]
            return [t for t in common_terms if t.startswith(text)]

        candidates = list(comp.COMMON_MODELS)
        if text.startswith("openrouter/") or (len(tokens) >= 2 and tokens[1].startswith("openrouter/")):
            try:
                dyn = ModelCatalog.get_completion_candidates(text)
                for d in dyn:
                    if d not in candidates:
                        candidates.append(d)
            except Exception:
                pass
        return [m for m in candidates if m.startswith(text)]

    # Inline @mention completion
    if text.startswith("@"):
        return [p for p in comp.get_personas() if p.startswith(text)]

    return []
