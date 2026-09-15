"""
Autonomic Action Tag Processor for Sympose Personas.
"""

import logging
import os
import re
import shutil
from typing import Any, ClassVar

from sympose.mcp import mcp_registry
from sympose.native_tools import NativeTools
from sympose.skills import skill_manager
from sympose.vault import VaultManager
from sympose.sub_agents import SubAgentEngine, SubAgentTask

log = logging.getLogger(__name__)


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

    @classmethod
    def parse_action_tags(cls, text: str) -> list[tuple[str, str, str]]:
        """Extracts all autonomic action tags supporting nested brackets while ignoring documentation template placeholders."""
        results: list[tuple[str, str, str]] = []
        i = 0
        while i < len(text):
            if text[i] == "[":
                for tag in cls.TAG_NAMES:
                    prefix = f"[{tag}:"
                    prefix_act = f"[ACTION:{tag}:"
                    p_len = 0
                    if text[i:].upper().startswith(prefix):
                        p_len = len(prefix)
                    elif text[i:].upper().startswith(prefix_act):
                        p_len = len(prefix_act)

                    if p_len > 0:
                        depth = 1
                        j = i + 1
                        while j < len(text) and depth > 0:
                            if text[j] == "[":
                                depth += 1
                            elif text[j] == "]":
                                depth -= 1
                            j += 1
                        if depth == 0:
                            raw_tag = text[i:j]
                            inner = text[i + p_len : j - 1].strip()
                            # Ignore documentation template placeholders (e.g. <handle>, <manifest>, <path>, etc.)
                            if not re.search(
                                r"<(?:handle|manifest|path|content|reflection_content|query|folder|key|value|target|spec)[^>]*>",
                                inner,
                                re.IGNORECASE,
                            ):
                                results.append((tag, inner, raw_tag))
                            i = j - 1
                        break
            i += 1
        return results

    @classmethod
    def strip_action_tags(cls, text: str) -> str:
        """Strips raw action tags from text without executing them."""
        tags = cls.parse_action_tags(text)
        clean = text
        for _, _, raw_tag in tags:
            clean = clean.replace(raw_tag, "")
        clean = re.sub(r"```[a-zA-Z0-9_-]*\s*```\n?", "", clean)
        return re.sub(r"\n{3,}", "\n\n", clean).strip()

    @classmethod
    def execute_actions(
        cls,
        profile_manager: Any,
        handle: str,
        text: str,
        user_prompt: str = "",
        depth: int = 0,
    ) -> tuple[str, list[str]]:
        """Executes all detected action tags in model output and returns (clean_text, confirmation_badges)."""
        is_sub_agent = handle.lower() == "sub_agent"
        profile = profile_manager.get_profile(handle) if not is_sub_agent else {}
        if not profile and not is_sub_agent:
            return text, []

        badges: list[str] = []
        name = "Sub-Agent" if is_sub_agent else profile.get("name", handle)
        vault_folder = profile.get("vault_folder", "")
        is_shared = profile.get("share_memory", False)

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

            # 1. WRITE_NOTE
            if tag == "WRITE_NOTE" and "|" in inner:
                parts = inner.split("|", 1)
                filename, content = parts[0].strip(), parts[1].strip()
                if filename and content:
                    result = VaultManager.write_note(profile, filename, content)
                    if cls._op_failed(result):
                        badges.append(f"> ⚠️ **{name} could not save note:** {result}")
                    else:
                        rel_path = (
                            f"{vault_folder}/{filename}" if vault_folder else filename
                        )
                        if not rel_path.endswith(".md"):
                            rel_path += ".md"
                        badges.append(
                            f"> 📝 **{name} saved note to Vault:** `{rel_path}`"
                        )

            # 2. APPEND_NOTE
            elif tag == "APPEND_NOTE" and "|" in inner:
                parts = inner.split("|", 1)
                filename, content = parts[0].strip(), parts[1].strip()
                if filename and content:
                    result = VaultManager.append_note(profile, filename, content)
                    if cls._op_failed(result):
                        badges.append(
                            f"> ⚠️ **{name} could not append to note:** {result}"
                        )
                    else:
                        rel_path = (
                            f"{vault_folder}/{filename}" if vault_folder else filename
                        )
                        if not rel_path.endswith(".md"):
                            rel_path += ".md"
                        badges.append(
                            f"> 📝 **{name} appended to Vault note:** `{rel_path}`"
                        )

            # 3. DAILY_NOTE
            elif tag == "DAILY_NOTE" and inner:
                result = VaultManager.write_daily_note(profile, inner)
                if cls._op_failed(result):
                    badges.append(
                        f"> ⚠️ **{name} could not log daily entry:** {result}"
                    )
                else:
                    badges.append(f"> 📅 **{name} logged entry to Daily Notes**")

            # 4. REMEMBER
            elif tag == "REMEMBER" and inner:
                ok = profile_manager.append_memory(handle, inner)
                if not ok:
                    badges.append(f"> ⚠️ **{name} could not persist to memory:** {inner}")
                else:
                    mem_desc = (
                        "working & shared team memory"
                        if is_shared
                        else f"private memory (`{profile.get('memory_file')}`)"
                    )
                    badges.append(f"> 🧠 **{name} updated {mem_desc}:** {inner}")

            # 4b. READ_NOTE / VIEW_NOTE
            elif tag in ("READ_NOTE", "VIEW_NOTE") and inner.strip():
                target_note = inner.strip().strip("\"'")
                rel_path, abs_path = VaultManager.resolve_note_target(
                    profile, target_note
                )
                if rel_path:
                    note_content = VaultManager.read_note(profile, rel_path)
                    if (
                        note_content is not None
                        and not str(note_content).startswith("Error")
                        and not str(note_content).startswith("⚠️")
                    ):
                        from sympose.config import config_manager

                        render_mode = (
                            str(config_manager.get("performance.render_mode", "hybrid"))
                            .lower()
                            .strip()
                        )
                        from sympose.ui import TerminalUI

                        console = (
                            TerminalUI.get_console() if render_mode != "raw" else None
                        )
                        TerminalUI.render_vault_note_panel(
                            console, rel_path, note_content
                        )
                        if is_sub_agent:
                            # The panel only reaches a terminal. Fold the verbatim
                            # text into the sub-agent's returned synthesis so the
                            # primary persona (and Slack) can quote it — otherwise a
                            # weak model answers from a plausible fake.
                            clean_text += (
                                f"\n\n### Ground-Truth Sandboxed Vault Note (`{rel_path}` — Exact Content):\n"
                                f"{str(note_content).strip()[:4000]}"
                            )
                        badges.append(
                            f"> 📄 **{name} rendered note to Terminal:** `{rel_path}`"
                        )
                    else:
                        badges.append(
                            f"> ⚠️ **Could not read note:** `{rel_path or target_note}`"
                        )
                else:
                    badges.append(
                        f"> ⚠️ **Note not found in allowed vault folders:** `{target_note}`"
                    )

            # 5. SPAWN_SUB_AGENT
            elif tag == "SPAWN_SUB_AGENT" and "|" in inner:
                parts = inner.split("|", 1)
                spec, task_prompt = parts[0].strip(), parts[1].strip()
                if task_prompt:
                    tokens = [
                        t.strip()
                        for t in spec.replace(";", ",").split(",")
                        if t.strip()
                    ]
                    skills_to_load = [
                        tok for tok in tokens if skill_manager.get_skill(tok)
                    ]
                    mcp_to_load = [
                        tok for tok in tokens if tok.lower() in mcp_registry.servers
                    ]
                    for tok in tokens:
                        if tok not in skills_to_load and tok not in mcp_to_load:
                            skills_to_load.append(tok)

                    task = SubAgentTask(
                        task_prompt=task_prompt,
                        skills=skills_to_load,
                        mcp_servers=mcp_to_load,
                        parent_agent=handle,
                    )
                    final_synthesis, tool_calls_executed = (
                        SubAgentEngine.execute_sub_agent_task(task)
                    )
                    if depth < cls.MAX_ACTION_DEPTH:
                        clean_sub_agent_res, sub_agent_sub_badges = cls.execute_actions(
                            profile_manager,
                            "sub_agent",
                            final_synthesis,
                            user_prompt=task_prompt,
                            depth=depth + 1,
                        )
                    else:
                        clean_sub_agent_res, sub_agent_sub_badges = (
                            cls.strip_action_tags(final_synthesis),
                            [],
                        )
                    for wb in sub_agent_sub_badges:
                        if wb not in badges:
                            badges.append(wb)

                    badge_spec = (
                        f"Skills: `{', '.join(skills_to_load)}`"
                        if skills_to_load
                        else (
                            f"MCP: `{', '.join(mcp_to_load)}`"
                            if mcp_to_load
                            else "General Sandbox"
                        )
                    )

                    report_md = [
                        f"> ### 🛠️ Sub-Agent Report `[{badge_spec}]`",
                        f"> **Task:** *{task_prompt}*",
                        "> ",
                        "> ---",
                        "> ",
                    ]
                    if tool_calls_executed:
                        tool_str = "  •  ".join(
                            [f"⚙️ `{tc}`" for tc in tool_calls_executed]
                        )
                        report_md.append(f"> {tool_str}")
                        report_md.append("> ")

                    for line in clean_sub_agent_res.strip().splitlines():
                        report_md.append(f"> {line}")

                    badges.append("\n" + "\n".join(report_md))

            # 5b. SEARCH / WEB_SEARCH (Direct in-turn live search)
            elif tag in ("SEARCH", "WEB_SEARCH") and inner.strip():
                query = inner.strip()
                ok, search_out = NativeTools.execute(
                    "web_search", {"query": query, "max_results": 5}
                )
                if ok and search_out:
                    indented_search = "\n".join(
                        [f"> {line}" for line in search_out.split("\n")]
                    )
                    badges.append(
                        f"\n> ### 🌐 Live Web Search Report (`{query}`)\n"
                        f"> \n"
                        f"> ---\n"
                        f"> \n"
                        f"{indented_search}"
                    )
                else:
                    badges.append(f"> 🌐 **Web Search (`{query}`):** *{search_out}*")

            # 6. CONFIG_SET
            elif tag == "CONFIG_SET" and "|" in inner:
                parts = inner.split("|", 1)
                key, raw_val = parts[0].strip(), parts[1].strip()
                if key and raw_val:
                    from sympose.config_schema import coerce, get_setting, validate

                    setting = get_setting(key)
                    if setting and setting.scope == "persona":
                        badges.append(
                            f"> ⚠️ **`{key}` is a per-persona setting** — use `/persona set @<handle> {key} <value>`, not runtime config."
                        )
                    else:
                        if setting:
                            try:
                                val: Any = coerce(setting, raw_val)
                            except ValueError as e:
                                badges.append(
                                    f"> ⚠️ **`[CONFIG_SET]` rejected:** `{key}` — {e}."
                                )
                                continue
                            ok, err = validate(key, val)
                            if not ok:
                                badges.append(
                                    f"> ⚠️ **`[CONFIG_SET]` rejected:** `{key}` {err}."
                                )
                                continue
                        else:
                            val = (
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
                        config_manager.set(key, val)
                        config_manager.save()
                        badges.append(
                            f"> ⚙️ **{name} updated runtime configuration:** `{key}` = `{val}`"
                        )

            # 7. CREATE_PERSONA
            elif tag == "CREATE_PERSONA":
                h_name, raw_yaml = "", ""
                if "|" in inner:
                    parts = inner.split("|", 1)
                    h_name, raw_yaml = (
                        parts[0].strip().lower().replace("@", ""),
                        parts[1].strip(),
                    )
                else:
                    raw_yaml = inner.strip()
                    try:
                        import yaml

                        y_data = yaml.safe_load(raw_yaml)
                        if isinstance(y_data, dict) and "handle" in y_data:
                            h_name = (
                                str(y_data["handle"]).strip().lower().replace("@", "")
                            )
                    except Exception as e:
                        log.debug(
                            "Persona manifest YAML parse failed, falling back to regex: %s",
                            e,
                        )
                    if not h_name:
                        m_h = re.search(
                            r"^handle:\s*([^\n\r]+)",
                            raw_yaml,
                            re.MULTILINE | re.IGNORECASE,
                        )
                        if m_h:
                            h_name = (
                                m_h.group(1)
                                .strip()
                                .strip("\"'")
                                .lower()
                                .replace("@", "")
                            )

                if h_name and raw_yaml:
                    p_dir = getattr(profile_manager, "profiles_dir", "profiles")
                    os.makedirs(p_dir, exist_ok=True)
                    yaml_file = os.path.join(p_dir, f"{h_name}.yaml")
                    try:
                        # `soul_content`, if present in the manifest, is the
                        # persona's actual Core Directives — pulled out and
                        # written to <handle>_soul.md directly, not left in
                        # the YAML. Without it, ProfileManager's own
                        # auto-bootstrap fallback (a single generic sentence)
                        # is all the new persona gets, discarding whatever
                        # reference-figure grounding the model described.
                        soul_content, manifest_yaml = None, raw_yaml
                        try:
                            import yaml

                            y_data = yaml.safe_load(raw_yaml)
                            if isinstance(y_data, dict) and "soul_content" in y_data:
                                soul_content = str(
                                    y_data.pop("soul_content") or ""
                                ).strip()
                                manifest_yaml = yaml.dump(
                                    y_data, default_flow_style=False, sort_keys=False
                                )
                        except Exception as e:
                            log.debug(
                                "Failed to split soul_content out of persona manifest: %s",
                                e,
                            )

                        with open(yaml_file, "w", encoding="utf-8") as f:
                            f.write(manifest_yaml)
                        if soul_content:
                            soul_file = os.path.join(p_dir, f"{h_name}_soul.md")
                            with open(soul_file, "w", encoding="utf-8") as f:
                                f.write(soul_content + "\n")

                        profile_manager.reload_profiles()
                        new_p = profile_manager.get_profile(h_name)
                        p_disp = new_p.get("name", h_name) if new_p else h_name
                        soul_note = " with a custom soul" if soul_content else ""
                        badges.append(
                            f"> 🧬 **{name} created new persona:** `@{h_name}` ({p_disp}){soul_note}"
                        )
                    except Exception as e:
                        badges.append(
                            f"> ⚠️ **Error creating persona `@{h_name}`:** {e}"
                        )
                else:
                    badges.append(
                        "> ⚠️ **Malformed `[CREATE_PERSONA]` action tag — ignored:** could not determine a handle from the provided YAML."
                    )

            # 8. DELETE_PERSONA
            elif tag == "DELETE_PERSONA" and inner:
                h_name = inner.strip().lower().replace("@", "")
                if h_name == "samantha":
                    badges.append(
                        "> ⚠️ **Protected Persona:** `@samantha` cannot be deleted."
                    )
                    continue
                p_dir = getattr(profile_manager, "profiles_dir", "profiles")
                arch_dir = os.path.join(p_dir, "_archived", h_name)
                files_to_move = []
                for ext in (".yaml", "_soul.md", "_memory.md"):
                    src = os.path.join(p_dir, f"{h_name}{ext}")
                    if os.path.exists(src):
                        files_to_move.append(
                            (src, os.path.join(arch_dir, f"{h_name}{ext}"))
                        )
                if files_to_move:
                    os.makedirs(arch_dir, exist_ok=True)
                    for src, dst in files_to_move:
                        try:
                            shutil.move(src, dst)
                        except Exception as e:
                            log.debug(
                                "[DELETE_PERSONA] failed to archive %s -> %s: %s",
                                src,
                                dst,
                                e,
                            )
                    profile_manager.reload_profiles()
                    if config_manager.get("runtime.default_persona") == h_name:
                        config_manager.set("runtime.default_persona", "samantha")
                        config_manager.save()

            elif tag == "WRITE_CANVAS" and "|" in inner:
                parts = inner.split("|", 1)
                target, content = parts[0].strip(), parts[1].strip()
                if target and content:
                    if (
                        target.startswith("#")
                        or target.startswith("C0")
                        or target.lower().startswith("slack:")
                    ):
                        # Slack Canvas API posting is not yet implemented.
                        # Emit an honest warning instead of a misleading success badge.
                        badges.append(
                            f"> ⚠️ **Slack Canvas posting not yet implemented** (target: `{target.replace('slack:', '').strip()}`). Canvas content was not sent."
                        )
                    else:
                        fname = (
                            target
                            if target.endswith(".canvas") or target.endswith(".md")
                            else f"{target}.canvas"
                        )
                        VaultManager.write_note(profile, fname, content)
                        rel_path = f"{vault_folder}/{fname}" if vault_folder else fname
                        badges.append(
                            f"> 🎨 **{name} created Visual Canvas in Vault:** `{rel_path}`"
                        )

            # ADR-071: a recognized tag whose shape didn't match any branch above
            # (e.g. `[WRITE_NOTE: filename]` with no `|content`) previously did
            # nothing silently — the model had no signal its action didn't run,
            # violating ground-truth sovereignty (ADR-024: don't let the model
            # believe unverified state). Surface it instead of swallowing it.
            elif tag in cls.TAG_NAMES:
                badges.append(
                    f"> ⚠️ **Malformed `[{tag}]` action tag — ignored (missing or invalid arguments).**"
                )

        clean_text = re.sub(r"```[a-zA-Z0-9_-]*\s*```\n?", "", clean_text)
        clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()
        return clean_text, badges
