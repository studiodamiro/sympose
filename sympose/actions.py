"""
Autonomic Action Tag Processor for Sympose Personas.

`execute_actions` used to be one function with a 14-branch if/elif chain
over tag names, each branch's full body inlined — mccabe flagged it at
complexity 66. Restructured the same way as `commands.py`'s `intercept`
(ADR-125 follow-up): each tag's body moved into its own `_handle_*`
method, dispatched through a small (gate, handler) table keyed by tag
name (`_tag_routes`) so `execute_actions` itself is just the tag loop
plus one table lookup, not 14 sequential `elif` branches. A handful of
handlers (`_handle_spawn_sub_agent`, `_handle_create_persona`,
`_handle_config_set`) were themselves complex enough to need a further
split into small helpers. Every handler shares its call's context
(profile, name, badges list, …) through `_ActionContext` instead of
closing over engine-turn locals, since — unlike `commands.py`'s
per-command handlers — several of these run recursively
(`SPAWN_SUB_AGENT` re-invokes `execute_actions` on sub-agent output).
"""

import logging
import os
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from sympose.config import config_manager
from sympose.mcp import mcp_registry
from sympose.native_tools import NativeTools
from sympose.skills import skill_manager
from sympose.vault import VaultManager
from sympose.sub_agents import SubAgentEngine, SubAgentTask

log = logging.getLogger(__name__)


@dataclass
class _ActionContext:
    """The per-call state every `_handle_*` tag handler needs, bundled so
    `execute_actions`'s dispatch loop can call any of them uniformly as
    `handler(ctx, inner)` regardless of what that particular tag actually
    reads or writes. `badges` is the same list object `execute_actions`
    returns — handlers append to it directly rather than returning their
    own list, since `SPAWN_SUB_AGENT` needs to de-duplicate a recursive
    call's badges against everything accumulated in this call so far."""

    profile_manager: Any
    handle: str
    profile: dict
    name: str
    vault_folder: str
    is_shared: bool
    is_sub_agent: bool
    user_prompt: str
    depth: int
    on_progress: Callable[[str], None] | None
    # ADR-130: fired once per completed action alongside its badge, with a
    # structured {"action": <TAG_NAME>, "detail": <str>} the dashboard's
    # streaming chat endpoint forwards as a distinct SSE event (the badge
    # string itself stays terminal/Slack's own rendering, unchanged).
    # None (every caller before ADR-130) means zero behavior change.
    on_action: Callable[[dict[str, str]], None] | None = None
    badges: list[str] = field(default_factory=list)


class ActionProcessor:
    """Parses, executes, and badges autonomic model action tags ([REMEMBER], [WRITE_NOTE], [DAILY_NOTE], [CONFIG_SET], etc.)."""

    TAG_NAMES: ClassVar[list[str]] = [
        "DAILY_NOTE",
        "WRITE_NOTE",
        "APPEND_NOTE",
        "REMEMBER",
        "READ_NOTE",
        "VIEW_NOTE",
        "SPAWN_SUB_AGENT",
        "SEARCH",
        "WEB_SEARCH",
        "CONFIG_SET",
        "CREATE_PERSONA",
        "DELETE_PERSONA",
        "WRITE_CANVAS",
        "REACT",
    ]

    # SPAWN_SUB_AGENT re-invokes execute_actions on sub-agent output; caps that
    # chain so a sub-agent synthesis containing another [SPAWN_SUB_AGENT: ...]
    # can't recurse unboundedly.
    MAX_ACTION_DEPTH = 1

    # Retired tag names from before the Worker -> Sub-Agent rename. An
    # unrecognized tag name isn't caught by any malformed-tag fallback — it
    # just silently prints as inert literal text instead of running (seen in
    # practice from weaker/local models reverting to the old spelling). This
    # catches the known case and turns it into a visible warning instead of a
    # silent no-op.
    _LEGACY_TAG_RE = re.compile(r"\[(?:ACTION:)?SPAWN_WORKER:[^\]]*\]", re.IGNORECASE)

    # A model can invent its own bracket notation that merely *looks* like
    # our tag syntax (e.g. `[GAME_STATE_UPDATE]`, seen live from a local
    # model narrating a roleplay game) - unlike a mistyped real tag, this
    # never matches any name in TAG_NAMES, so parse_action_tags never sees
    # it and it just prints as raw literal text. Caught by shape (an
    # all-caps, underscored identifier alone in brackets - the same
    # structural pattern every real tag name follows) rather than by
    # enumerating every name a model might dream up; real tag names are
    # excluded so an already-handled tag's own bracket is never touched
    # here even if something upstream left it unprocessed.
    _PSEUDO_TAG_RE = re.compile(
        r"\[(?:ACTION:)?(?!(?:" + "|".join(TAG_NAMES) + r")\b)"
        r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+(?::[^\]]*)?\]"
    )

    @staticmethod
    def _op_failed(result: str) -> bool:
        """True when a vault_write.py-style call returned one of its
        established failure prefixes instead of a success message. Every
        call site that shows a confirmation badge must check this first —
        write_note/append_note/write_daily_note return a string either way,
        and nothing upstream previously distinguished them, so a rejected
        write (sandbox violation, the Daily/ boundary guard, a disk error)
        was confirmed to the user as a success every time."""
        return isinstance(result, str) and result.startswith(
            ("Error", "Security Error", "Warning")
        )

    @staticmethod
    def _match_tag_prefix(text: str, i: int, tag: str) -> int:
        """Length of a `[TAG:` or `[ACTION:TAG:` prefix at position `i`
        (case-insensitive), or 0 if neither matches."""
        prefix = f"[{tag}:"
        prefix_act = f"[ACTION:{tag}:"
        upper = text[i:].upper()
        if upper.startswith(prefix):
            return len(prefix)
        if upper.startswith(prefix_act):
            return len(prefix_act)
        return 0

    @staticmethod
    def _find_matching_bracket(text: str, start: int) -> int | None:
        """Index just past the `]` that closes the `[` at `start`, counting
        nested brackets - or None if it's never closed before the text
        ends."""
        depth = 1
        j = start + 1
        while j < len(text) and depth > 0:
            if text[j] == "[":
                depth += 1
            elif text[j] == "]":
                depth -= 1
            j += 1
        return j if depth == 0 else None

    @classmethod
    def _consume_tag_at(
        cls, text: str, i: int, results: list[tuple[str, str, str]]
    ) -> int:
        """If a recognized tag starts at `i`, parses it (appending to
        `results` unless it's a documentation template placeholder) and
        returns the index of its closing `]`, so the outer scan can resume
        just past it; otherwise returns `i` unchanged (an unrecognized or
        never-closed bracket is left for the outer scan to step past one
        character at a time, same as plain literal text)."""
        for tag in cls.TAG_NAMES:
            p_len = cls._match_tag_prefix(text, i, tag)
            if not p_len:
                continue
            j = cls._find_matching_bracket(text, i)
            if j is None:
                break
            raw_tag = text[i:j]
            inner = text[i + p_len : j - 1].strip()
            # Ignore documentation template placeholders (e.g. <handle>, <manifest>, <path>, etc.)
            if not re.search(
                r"<(?:handle|manifest|path|content|reflection_content|query|folder|key|value|target|spec)[^>]*>",
                inner,
                re.IGNORECASE,
            ):
                results.append((tag, inner, raw_tag))
            return j - 1
        return i

    @classmethod
    def parse_action_tags(cls, text: str) -> list[tuple[str, str, str]]:
        """Extracts all autonomic action tags supporting nested brackets while ignoring documentation template placeholders."""
        results: list[tuple[str, str, str]] = []
        i = 0
        while i < len(text):
            if text[i] == "[":
                i = cls._consume_tag_at(text, i, results)
            i += 1
        return results

    @classmethod
    def strip_action_tags(cls, text: str) -> str:
        """Strips raw action tags from text without executing them."""
        tags = cls.parse_action_tags(text)
        clean = text
        for _, _, raw_tag in tags:
            clean = clean.replace(raw_tag, "")
        clean = cls._PSEUDO_TAG_RE.sub("", clean)
        clean = re.sub(r"```[a-zA-Z0-9_-]*\s*```\n?", "", clean)
        return re.sub(r"\n{3,}", "\n\n", clean).strip()

    # --- Tag-shape gates: does a tag's body look well-formed enough to run
    # its handler at all? False falls through to the generic malformed-tag
    # badge in execute_actions, matching each tag's own historical
    # condition (e.g. WRITE_NOTE needs a `|` separator; DAILY_NOTE just
    # needs a non-empty body; CREATE_PERSONA has no shape requirement).
    @staticmethod
    def _has_pipe(inner: str) -> bool:
        return "|" in inner

    @staticmethod
    def _non_empty(inner: str) -> bool:
        return bool(inner)

    @staticmethod
    def _non_empty_stripped(inner: str) -> bool:
        return bool(inner.strip())

    @staticmethod
    def _always_true(inner: str) -> bool:
        return True

    @classmethod
    def _tag_routes(
        cls,
    ) -> dict[str, tuple[Callable[[str], bool], Callable[["_ActionContext", str], str]]]:
        """(gate, handler) per tag name. Handlers return the text (if any)
        to append to `clean_text`; badges are appended to `ctx.badges`
        directly by the handler itself. READ_NOTE/VIEW_NOTE and
        SEARCH/WEB_SEARCH are pairs of tag spellings sharing one handler."""
        return {
            "WRITE_NOTE": (cls._has_pipe, cls._handle_write_note),
            "APPEND_NOTE": (cls._has_pipe, cls._handle_append_note),
            "DAILY_NOTE": (cls._non_empty, cls._handle_daily_note),
            "REMEMBER": (cls._non_empty, cls._handle_remember),
            "READ_NOTE": (cls._non_empty_stripped, cls._handle_read_note),
            "VIEW_NOTE": (cls._non_empty_stripped, cls._handle_read_note),
            "SPAWN_SUB_AGENT": (cls._has_pipe, cls._handle_spawn_sub_agent),
            "SEARCH": (cls._non_empty_stripped, cls._handle_search),
            "WEB_SEARCH": (cls._non_empty_stripped, cls._handle_search),
            "CONFIG_SET": (cls._has_pipe, cls._handle_config_set),
            "CREATE_PERSONA": (cls._always_true, cls._handle_create_persona),
            "DELETE_PERSONA": (cls._non_empty, cls._handle_delete_persona),
            "WRITE_CANVAS": (cls._has_pipe, cls._handle_write_canvas),
        }

    # --- 1. WRITE_NOTE / 2. APPEND_NOTE -------------------------------------
    @staticmethod
    def _handle_write_note(ctx: _ActionContext, inner: str) -> str:
        parts = inner.split("|", 1)
        filename, content = parts[0].strip(), parts[1].strip()
        if filename and content:
            result = VaultManager.write_note(ctx.profile, filename, content)
            if ActionProcessor._op_failed(result):
                ctx.badges.append(f"> ⚠️ **{ctx.name} could not save note:** {result}")
            else:
                rel_path = (
                    f"{ctx.vault_folder}/{filename}" if ctx.vault_folder else filename
                )
                if not rel_path.endswith(".md"):
                    rel_path += ".md"
                ctx.badges.append(f"> 📝 **{ctx.name} saved note to Vault:** `{rel_path}`")
                if ctx.on_action:
                    ctx.on_action({"action": "WRITE_NOTE", "detail": rel_path})
        return ""

    @staticmethod
    def _handle_append_note(ctx: _ActionContext, inner: str) -> str:
        parts = inner.split("|", 1)
        filename, content = parts[0].strip(), parts[1].strip()
        if filename and content:
            result = VaultManager.append_note(ctx.profile, filename, content)
            if ActionProcessor._op_failed(result):
                ctx.badges.append(
                    f"> ⚠️ **{ctx.name} could not append to note:** {result}"
                )
            else:
                rel_path = (
                    f"{ctx.vault_folder}/{filename}" if ctx.vault_folder else filename
                )
                if not rel_path.endswith(".md"):
                    rel_path += ".md"
                ctx.badges.append(
                    f"> 📝 **{ctx.name} appended to Vault note:** `{rel_path}`"
                )
                if ctx.on_action:
                    ctx.on_action({"action": "APPEND_NOTE", "detail": rel_path})
        return ""

    # --- 3. DAILY_NOTE -------------------------------------------------------
    @staticmethod
    def _handle_daily_note(ctx: _ActionContext, inner: str) -> str:
        result = VaultManager.write_daily_note(ctx.profile, inner)
        if ActionProcessor._op_failed(result):
            ctx.badges.append(f"> ⚠️ **{ctx.name} could not log daily entry:** {result}")
        else:
            ctx.badges.append(f"> 📅 **{ctx.name} logged entry to Daily Notes**")
            if ctx.on_action:
                ctx.on_action({"action": "DAILY_NOTE", "detail": ""})
        return ""

    # --- 4. REMEMBER -----------------------------------------------------------
    @staticmethod
    def _handle_remember(ctx: _ActionContext, inner: str) -> str:
        ok = ctx.profile_manager.append_memory(ctx.handle, inner)
        if not ok:
            ctx.badges.append(f"> ⚠️ **{ctx.name} could not persist to memory:** {inner}")
        else:
            mem_desc = (
                "working & shared team memory"
                if ctx.is_shared
                else f"private memory (`{ctx.profile.get('memory_file')}`)"
            )
            ctx.badges.append(f"> 🧠 **{ctx.name} updated {mem_desc}:** {inner}")
        return ""

    # --- 4b. READ_NOTE / VIEW_NOTE ---------------------------------------------
    @staticmethod
    def _handle_read_note(ctx: _ActionContext, inner: str) -> str:
        target_note = inner.strip().strip("\"'")
        rel_path, _abs_path = VaultManager.resolve_note_target(ctx.profile, target_note)
        if not rel_path:
            ctx.badges.append(
                f"> ⚠️ **Note not found in allowed vault folders:** `{target_note}`"
            )
            return ""

        note_content = VaultManager.read_note(ctx.profile, rel_path)
        if (
            note_content is None
            or str(note_content).startswith("Error")
            or str(note_content).startswith("⚠️")
        ):
            ctx.badges.append(f"> ⚠️ **Could not read note:** `{rel_path or target_note}`")
            return ""

        render_mode = (
            str(config_manager.get("performance.render_mode", "hybrid")).lower().strip()
        )
        from sympose.ui import TerminalUI

        console = TerminalUI.get_console() if render_mode != "raw" else None
        TerminalUI.render_vault_note_panel(console, rel_path, note_content)

        extra_text = ""
        if ctx.is_sub_agent:
            # The panel only reaches a terminal. Fold the verbatim text into
            # the sub-agent's returned synthesis so the primary persona (and
            # Slack) can quote it — otherwise a weak model answers from a
            # plausible fake.
            extra_text = (
                f"\n\n### Ground-Truth Sandboxed Vault Note (`{rel_path}` — Exact Content):\n"
                f"{str(note_content).strip()[:4000]}"
            )
        ctx.badges.append(f"> 📄 **{ctx.name} rendered note to Terminal:** `{rel_path}`")
        return extra_text

    # --- 5. SPAWN_SUB_AGENT -----------------------------------------------------
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

    @classmethod
    def _handle_spawn_sub_agent(cls, ctx: _ActionContext, inner: str) -> str:
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
        if ctx.on_action:
            ctx.on_action({"action": "SPAWN_SUB_AGENT", "detail": badge_spec})
        return ""

    # --- 5b. SEARCH / WEB_SEARCH (Direct in-turn live search) -------------------
    @staticmethod
    def _handle_search(ctx: _ActionContext, inner: str) -> str:
        query = inner.strip()
        ok, search_out = NativeTools.execute(
            "web_search", {"query": query, "max_results": 5}
        )
        if ok and search_out:
            indented_search = "\n".join([f"> {line}" for line in search_out.split("\n")])
            ctx.badges.append(
                f"\n> ### 🌐 Live Web Search Report (`{query}`)\n"
                f"> \n"
                f"> ---\n"
                f"> \n"
                f"{indented_search}"
            )
            if ctx.on_action:
                ctx.on_action({"action": "SEARCH", "detail": query})
        else:
            ctx.badges.append(f"> 🌐 **Web Search (`{query}`):** *{search_out}*")
        return ""

    # --- 6. CONFIG_SET -----------------------------------------------------------
    @staticmethod
    def _coerce_unknown_config_value(raw_val: str) -> Any:
        """Best-effort type guess for a CONFIG_SET value with no schema
        entry: bool keywords, then int, then float, falling back to the raw
        string."""
        val: Any = (
            True
            if raw_val.lower() == "true"
            else (False if raw_val.lower() == "false" else raw_val)
        )
        try:
            val = int(raw_val)
        except ValueError:
            try:
                val = float(raw_val)
            except ValueError:
                pass
        return val

    @staticmethod
    def _handle_config_set(ctx: _ActionContext, inner: str) -> str:
        parts = inner.split("|", 1)
        key, raw_val = parts[0].strip(), parts[1].strip()
        if not (key and raw_val):
            return ""

        from sympose.config_schema import coerce, get_setting, validate

        setting = get_setting(key)
        if setting and setting.scope == "persona":
            ctx.badges.append(
                f"> ⚠️ **`{key}` is a per-persona setting** — use `/persona set @<handle> {key} <value>`, not runtime config."
            )
            return ""

        if setting:
            try:
                val: Any = coerce(setting, raw_val)
            except ValueError as e:
                ctx.badges.append(f"> ⚠️ **`[CONFIG_SET]` rejected:** `{key}` — {e}.")
                return ""
            ok, err = validate(key, val)
            if not ok:
                ctx.badges.append(f"> ⚠️ **`[CONFIG_SET]` rejected:** `{key}` {err}.")
                return ""
        else:
            val = ActionProcessor._coerce_unknown_config_value(raw_val)

        config_manager.set(key, val)
        config_manager.save()
        ctx.badges.append(
            f"> ⚙️ **{ctx.name} updated runtime configuration:** `{key}` = `{val}`"
        )
        if ctx.on_action:
            ctx.on_action({"action": "CONFIG_SET", "detail": key})
        return ""

    # --- 7. CREATE_PERSONA -------------------------------------------------------
    @staticmethod
    def _parse_persona_manifest(inner: str) -> tuple[str, str]:
        """Extracts (handle, raw_yaml) from a CREATE_PERSONA tag's body:
        either an explicit `handle|yaml` pipe form, or a bare YAML manifest
        whose `handle:` field is read out (via YAML parse, falling back to a
        regex scan if the YAML doesn't parse)."""
        if "|" in inner:
            parts = inner.split("|", 1)
            return parts[0].strip().lower().replace("@", ""), parts[1].strip()

        raw_yaml = inner.strip()
        h_name = ""
        try:
            import yaml

            y_data = yaml.safe_load(raw_yaml)
            if isinstance(y_data, dict) and "handle" in y_data:
                h_name = str(y_data["handle"]).strip().lower().replace("@", "")
        except Exception as e:
            log.debug(
                "Persona manifest YAML parse failed, falling back to regex: %s", e
            )
        if not h_name:
            m_h = re.search(
                r"^handle:\s*([^\n\r]+)", raw_yaml, re.MULTILINE | re.IGNORECASE
            )
            if m_h:
                h_name = m_h.group(1).strip().strip("\"'").lower().replace("@", "")
        return h_name, raw_yaml

    @staticmethod
    def _split_soul_content(raw_yaml: str) -> tuple[str | None, str]:
        """Pulls a `soul_content` field out of a persona manifest YAML, if
        present, so it can be written to <handle>_soul.md directly instead
        of left in the YAML - without it, ProfileManager's own
        auto-bootstrap fallback (a single generic sentence) is all the new
        persona gets, discarding whatever reference-figure grounding the
        model described. Returns (soul_content_or_None, remaining_manifest_yaml)."""
        soul_content, manifest_yaml = None, raw_yaml
        try:
            import yaml

            y_data = yaml.safe_load(raw_yaml)
            if isinstance(y_data, dict) and "soul_content" in y_data:
                soul_content = str(y_data.pop("soul_content") or "").strip()
                manifest_yaml = yaml.dump(
                    y_data, default_flow_style=False, sort_keys=False
                )
        except Exception as e:
            log.debug("Failed to split soul_content out of persona manifest: %s", e)
        return soul_content, manifest_yaml

    @staticmethod
    def _handle_create_persona(ctx: _ActionContext, inner: str) -> str:
        h_name, raw_yaml = ActionProcessor._parse_persona_manifest(inner)
        if not (h_name and raw_yaml):
            ctx.badges.append(
                "> ⚠️ **Malformed `[CREATE_PERSONA]` action tag — ignored:** could not determine a handle from the provided YAML."
            )
            return ""

        p_dir = getattr(ctx.profile_manager, "profiles_dir", "profiles")
        os.makedirs(p_dir, exist_ok=True)
        yaml_file = os.path.join(p_dir, f"{h_name}.yaml")
        try:
            soul_content, manifest_yaml = ActionProcessor._split_soul_content(raw_yaml)
            with open(yaml_file, "w", encoding="utf-8") as f:
                f.write(manifest_yaml)
            if soul_content:
                soul_file = os.path.join(p_dir, f"{h_name}_soul.md")
                with open(soul_file, "w", encoding="utf-8") as f:
                    f.write(soul_content + "\n")

            ctx.profile_manager.reload_profiles()
            new_p = ctx.profile_manager.get_profile(h_name)
            p_disp = new_p.get("name", h_name) if new_p else h_name
            soul_note = " with a custom soul" if soul_content else ""
            ctx.badges.append(
                f"> 🧬 **{ctx.name} created new persona:** `@{h_name}` ({p_disp}){soul_note}"
            )
            if ctx.on_action:
                ctx.on_action({"action": "CREATE_PERSONA", "detail": f"@{h_name}"})
        except Exception as e:
            ctx.badges.append(f"> ⚠️ **Error creating persona `@{h_name}`:** {e}")
        return ""

    # --- 8. DELETE_PERSONA ---------------------------------------------------------
    @staticmethod
    def _handle_delete_persona(ctx: _ActionContext, inner: str) -> str:
        h_name = inner.strip().lower().replace("@", "")
        if h_name == "samantha":
            ctx.badges.append(
                "> ⚠️ **Protected Persona:** `@samantha` cannot be deleted."
            )
            return ""

        p_dir = getattr(ctx.profile_manager, "profiles_dir", "profiles")
        arch_dir = os.path.join(p_dir, "_archived", h_name)
        files_to_move = []
        for ext in (".yaml", "_soul.md", "_memory.md"):
            src = os.path.join(p_dir, f"{h_name}{ext}")
            if os.path.exists(src):
                files_to_move.append((src, os.path.join(arch_dir, f"{h_name}{ext}")))

        if not files_to_move:
            ctx.badges.append(f"> ⚠️ **Persona `@{h_name}` not found** — nothing deleted.")
            return ""

        os.makedirs(arch_dir, exist_ok=True)
        for src, dst in files_to_move:
            try:
                shutil.move(src, dst)
            except Exception as e:
                log.debug(
                    "[DELETE_PERSONA] failed to archive %s -> %s: %s", src, dst, e
                )
        ctx.profile_manager.reload_profiles()
        if config_manager.get("runtime.default_persona") == h_name:
            config_manager.set("runtime.default_persona", "samantha")
            config_manager.save()
        ctx.badges.append(
            f"> 🗑️ **{ctx.name} deleted persona:** `@{h_name}` (archived, not permanently erased)"
        )
        if ctx.on_action:
            ctx.on_action({"action": "DELETE_PERSONA", "detail": f"@{h_name}"})
        return ""

    # --- WRITE_CANVAS -----------------------------------------------------------
    @staticmethod
    def _handle_write_canvas(ctx: _ActionContext, inner: str) -> str:
        parts = inner.split("|", 1)
        target, content = parts[0].strip(), parts[1].strip()
        if not (target and content):
            return ""

        if (
            target.startswith("#")
            or target.startswith("C0")
            or target.lower().startswith("slack:")
        ):
            # Slack Canvas API posting is not yet implemented. Emit an
            # honest warning instead of a misleading success badge.
            ctx.badges.append(
                f"> ⚠️ **Slack Canvas posting not yet implemented** (target: `{target.replace('slack:', '').strip()}`). Canvas content was not sent."
            )
            return ""

        fname = (
            target
            if target.endswith(".canvas") or target.endswith(".md")
            else f"{target}.canvas"
        )
        result = VaultManager.write_note(ctx.profile, fname, content)
        if ActionProcessor._op_failed(result):
            ctx.badges.append(f"> ⚠️ **{ctx.name} could not save Visual Canvas:** {result}")
        else:
            rel_path = f"{ctx.vault_folder}/{fname}" if ctx.vault_folder else fname
            ctx.badges.append(
                f"> 🎨 **{ctx.name} created Visual Canvas in Vault:** `{rel_path}`"
            )
        return ""

    @classmethod
    def execute_actions(
        cls,
        profile_manager: Any,
        handle: str,
        text: str,
        user_prompt: str = "",
        depth: int = 0,
        on_progress: Callable[[str], None] | None = None,
        on_action: Callable[[dict[str, str]], None] | None = None,
    ) -> tuple[str, list[str]]:
        """Executes all detected action tags in model output and returns
        (clean_text, confirmation_badges). `on_progress`, if given, is passed
        straight through to a spawned sub-agent's tool-call loop so a caller
        can show live progress during what would otherwise be a silent,
        multi-turn synchronous wait — see SubAgentEngine.execute_sub_agent_task.
        `on_action`, if given (ADR-130), fires once per completed action tag
        with a structured `{"action": <TAG_NAME>, "detail": <str>}` — the
        dashboard's streaming chat endpoint uses this to emit a distinct SSE
        event per action; `None` (every caller before ADR-130) is a no-op."""
        is_sub_agent = handle.lower() == "sub_agent"
        profile = profile_manager.get_profile(handle) if not is_sub_agent else {}
        if not profile and not is_sub_agent:
            return text, []

        name = "Sub-Agent" if is_sub_agent else profile.get("name", handle)
        ctx = _ActionContext(
            profile_manager=profile_manager,
            handle=handle,
            profile=profile,
            name=name,
            vault_folder=profile.get("vault_folder", ""),
            is_shared=profile.get("share_memory", False),
            is_sub_agent=is_sub_agent,
            user_prompt=user_prompt,
            depth=depth,
            on_progress=on_progress,
            on_action=on_action,
        )
        badges = ctx.badges

        tags = cls.parse_action_tags(text)
        clean_text = text

        legacy_matches = cls._LEGACY_TAG_RE.findall(clean_text)
        if legacy_matches:
            clean_text = cls._LEGACY_TAG_RE.sub("", clean_text)
            badges.append(
                f"> ⚠️ **{name} used the retired `[SPAWN_WORKER]` tag — nothing "
                "was dispatched.** The current sub-agent tag is "
                "`[SPAWN_SUB_AGENT: ...]`."
            )

        routes = cls._tag_routes()
        # A model that repeats itself (common with weaker/local models) can
        # emit the exact same tag twice — the text strip below is already
        # idempotent, but without this guard the tag's real side effect
        # (writing/appending a note, spawning a sub-agent, remembering a fact)
        # would otherwise fire once per repeated occurrence.
        seen_raw_tags: set[str] = set()

        for tag, inner, raw_tag in tags:
            clean_text = clean_text.replace(raw_tag, "")
            if raw_tag in seen_raw_tags:
                continue
            seen_raw_tags.add(raw_tag)

            # REACT is handled upstream by slack.py, which regex-matches it
            # directly against the raw model output to drive emoji reactions
            # (see strip_action_tags). It reaches this loop as an already
            # recognized, already handled tag — no-op it here rather than
            # falling into the malformed-tag branch below.
            if tag == "REACT":
                continue

            route = routes.get(tag)
            if route and route[0](inner):
                clean_text += route[1](ctx, inner)
            elif tag in cls.TAG_NAMES:
                # ADR-071: a recognized tag whose shape didn't match its
                # handler's gate (e.g. `[WRITE_NOTE: filename]` with no
                # `|content`) previously did nothing silently — the model
                # had no signal its action didn't run, violating
                # ground-truth sovereignty (ADR-024: don't let the model
                # believe unverified state). Surface it instead of
                # swallowing it.
                badges.append(
                    f"> ⚠️ **Malformed `[{tag}]` action tag — ignored (missing or invalid arguments).**"
                )

        clean_text = cls._PSEUDO_TAG_RE.sub("", clean_text)
        clean_text = re.sub(r"```[a-zA-Z0-9_-]*\s*```\n?", "", clean_text)
        clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()
        return clean_text, badges
