"""
Autonomic Action Tag Processor for Sympose Agents.
"""

import os
import shutil
import re
from typing import Dict, Any, List, Tuple
from sympose.vault import VaultManager
from sympose.skills import skill_manager
from sympose.workers import WorkerEngine, WorkerTask
from sympose.mcp import mcp_registry
from sympose.config import config_manager
from sympose.native_tools import NativeTools


class ActionProcessor:
    """Parses, executes, and badges autonomic model action tags ([REMEMBER], [WRITE_NOTE], [DAILY_NOTE], [CONFIG_SET], etc.)."""

    TAG_NAMES = [
        "DAILY_NOTE", "WRITE_NOTE", "APPEND_NOTE", "REMEMBER",
        "READ_NOTE", "VIEW_NOTE",
        "SPAWN_WORKER", "SEARCH", "WEB_SEARCH", "CONFIG_SET",
        "CREATE_PERSONA", "DELETE_PERSONA", "WRITE_CANVAS", "REACT"
    ]

    @classmethod
    def parse_action_tags(cls, text: str) -> List[Tuple[str, str, str]]:
        """Extracts all autonomic action tags supporting nested brackets while ignoring documentation template placeholders."""
        results: List[Tuple[str, str, str]] = []
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
                            inner = text[i + p_len:j - 1].strip()
                            # Ignore documentation template placeholders (e.g. <handle>, <manifest>, <path>, etc.)
                            if not re.search(r"<(?:handle|manifest|path|content|reflection_content|query|folder|key|value|target|spec)[^>]*>", inner, re.I):
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
    def execute_actions(cls, profile_manager: Any, handle: str, text: str, user_prompt: str = "") -> Tuple[str, List[str]]:
        """Executes all detected action tags in model output and returns (clean_text, confirmation_badges)."""
        is_worker = (handle.lower() == "worker")
        profile = profile_manager.get_profile(handle) if not is_worker else {}
        if not profile and not is_worker:
            return text, []

        badges: List[str] = []
        name = "Sub-Agent Worker" if is_worker else profile.get("name", handle)
        vault_folder = profile.get("vault_folder", "")
        is_shared = profile.get("share_memory", False)

        tags = cls.parse_action_tags(text)
        clean_text = text

        has_daily_note_tag = False

        for tag, inner, raw_tag in tags:
            clean_text = clean_text.replace(raw_tag, "")

            # 1. WRITE_NOTE
            if tag == "WRITE_NOTE" and "|" in inner:
                parts = inner.split("|", 1)
                filename, content = parts[0].strip(), parts[1].strip()
                if filename and content:
                    VaultManager.write_note(profile, filename, content)
                    rel_path = f"{vault_folder}/{filename}" if vault_folder else filename
                    if not rel_path.endswith(".md"): rel_path += ".md"
                    badges.append(f"> 📝 **{name} saved note to Vault:** `{rel_path}`")

            # 2. APPEND_NOTE
            elif tag == "APPEND_NOTE" and "|" in inner:
                parts = inner.split("|", 1)
                filename, content = parts[0].strip(), parts[1].strip()
                if filename and content:
                    VaultManager.append_note(profile, filename, content)
                    rel_path = f"{vault_folder}/{filename}" if vault_folder else filename
                    if not rel_path.endswith(".md"): rel_path += ".md"
                    badges.append(f"> 📝 **{name} appended to Vault note:** `{rel_path}`")

            # 3. DAILY_NOTE
            elif tag == "DAILY_NOTE" and inner:
                has_daily_note_tag = True
                VaultManager.write_daily_note(profile, inner)
                badges.append(f"> 📅 **{name} logged entry to Daily Notes**")

            # 4. REMEMBER
            elif tag == "REMEMBER" and inner:
                profile_manager.append_memory(handle, inner)
                mem_desc = "working & shared team memory" if is_shared else f"private memory (`{profile.get('memory_file')}`)"
                badges.append(f"> 🧠 **{name} updated {mem_desc}:** {inner}")

            # 4b. READ_NOTE / VIEW_NOTE
            elif tag in ("READ_NOTE", "VIEW_NOTE") and inner.strip():
                target_note = inner.strip().strip("\"'")
                rel_path, abs_path = VaultManager.resolve_note_target(profile, target_note)
                if rel_path:
                    note_content = VaultManager.read_note(profile, rel_path)
                    if note_content is not None and not str(note_content).startswith("Error") and not str(note_content).startswith("⚠️"):
                        from sympose.config import config_manager
                        render_mode = str(config_manager.get("performance.render_mode", "hybrid")).lower().strip()
                        from sympose.ui import TerminalUI
                        console = TerminalUI.get_console() if render_mode != "raw" else None
                        TerminalUI.render_vault_note_panel(console, rel_path, note_content)
                        badges.append(f"> 📄 **{name} rendered note to Terminal:** `{rel_path}`")
                    else:
                        badges.append(f"> ⚠️ **Could not read note:** `{rel_path or target_note}`")
                else:
                    badges.append(f"> ⚠️ **Note not found in allowed vault folders:** `{target_note}`")

            # 5. SPAWN_WORKER
            elif tag == "SPAWN_WORKER" and "|" in inner:
                parts = inner.split("|", 1)
                spec, task_prompt = parts[0].strip(), parts[1].strip()
                if task_prompt:
                    tokens = [t.strip() for t in spec.replace(";", ",").split(",") if t.strip()]
                    skills_to_load = [tok for tok in tokens if skill_manager.get_skill(tok)]
                    mcp_to_load = [tok for tok in tokens if tok.lower() in mcp_registry.servers]
                    for tok in tokens:
                        if tok not in skills_to_load and tok not in mcp_to_load:
                            skills_to_load.append(tok)

                    task = WorkerTask(
                        task_prompt=task_prompt,
                        skills=skills_to_load,
                        mcp_servers=mcp_to_load,
                        parent_agent=handle,
                    )
                    final_synthesis, tool_calls_executed = WorkerEngine.execute_worker_task(task)
                    clean_worker_res, worker_sub_badges = cls.execute_actions(profile_manager, "worker", final_synthesis, user_prompt=task_prompt)
                    for wb in worker_sub_badges:
                        if wb not in badges:
                            badges.append(wb)

                    badge_spec = f"Skills: `{', '.join(skills_to_load)}`" if skills_to_load else (f"MCP: `{', '.join(mcp_to_load)}`" if mcp_to_load else "General Sandbox")

                    report_md = [
                        f"> ### 🛠️ Sub-Agent Worker Report `[{badge_spec}]`",
                        f"> **Task:** *{task_prompt}*",
                        "> ",
                        "> ---",
                        "> "
                    ]
                    if tool_calls_executed:
                        tool_str = "  •  ".join([f"⚙️ `{tc}`" for tc in tool_calls_executed])
                        report_md.append(f"> {tool_str}")
                        report_md.append("> ")

                    for line in clean_worker_res.strip().splitlines():
                        report_md.append(f"> {line}")

                    badges.append("\n" + "\n".join(report_md))

            # 5b. SEARCH / WEB_SEARCH (Direct in-turn live search)
            elif tag in ("SEARCH", "WEB_SEARCH") and inner.strip():
                query = inner.strip()
                ok, search_out = NativeTools.execute("web_search", {"query": query, "max_results": 5})
                if ok and search_out:
                    indented_search = "\n".join([f"> {line}" for line in search_out.split("\n")])
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
                    val: Any = True if raw_val.lower() == "true" else (False if raw_val.lower() == "false" else raw_val)
                    try: val = int(raw_val)
                    except ValueError:
                        try: val = float(raw_val)
                        except ValueError: pass
                    config_manager.set(key, val)
                    config_manager.save()
                    badges.append(f"> ⚙️ **{name} updated runtime configuration:** `{key}` = `{val}`")

            # 7. CREATE_PERSONA
            elif tag == "CREATE_PERSONA":
                h_name, raw_yaml = "", ""
                if "|" in inner:
                    parts = inner.split("|", 1)
                    h_name, raw_yaml = parts[0].strip().lower().replace("@", ""), parts[1].strip()
                else:
                    raw_yaml = inner.strip()
                    try:
                        import yaml
                        y_data = yaml.safe_load(raw_yaml)
                        if isinstance(y_data, dict) and "handle" in y_data:
                            h_name = str(y_data["handle"]).strip().lower().replace("@", "")
                    except Exception:
                        pass
                    if not h_name:
                        m_h = re.search(r"^handle:\s*([^\n\r]+)", raw_yaml, re.M | re.I)
                        if m_h:
                            h_name = m_h.group(1).strip().strip("\"'").lower().replace("@", "")

                if h_name and raw_yaml:
                    p_dir = getattr(profile_manager, "profiles_dir", "profiles")
                    os.makedirs(p_dir, exist_ok=True)
                    yaml_file = os.path.join(p_dir, f"{h_name}.yaml")
                    try:
                        with open(yaml_file, "w", encoding="utf-8") as f:
                            f.write(raw_yaml)
                        profile_manager.reload_profiles()
                        new_p = profile_manager.get_profile(h_name)
                        p_disp = new_p.get("name", h_name) if new_p else h_name
                        badges.append(f"> 🧬 **{name} created new agent persona:** `@{h_name}` ({p_disp})")
                    except Exception as e:
                        badges.append(f"> ⚠️ **Error creating persona `@{h_name}`:** {e}")

            # 8. DELETE_PERSONA
            elif tag == "DELETE_PERSONA" and inner:
                h_name = inner.strip().lower().replace("@", "")
                if h_name == "samantha":
                    badges.append(f"> ⚠️ **Protected Persona:** `@samantha` cannot be deleted.")
                    continue
                p_dir = getattr(profile_manager, "profiles_dir", "profiles")
                arch_dir = os.path.join(p_dir, "_archived", h_name)
                files_to_move = []
                for ext in (".yaml", "_soul.md", "_memory.md"):
                    src = os.path.join(p_dir, f"{h_name}{ext}")
                    if os.path.exists(src):
                        files_to_move.append((src, os.path.join(arch_dir, f"{h_name}{ext}")))
                if files_to_move:
                    os.makedirs(arch_dir, exist_ok=True)
                    for src, dst in files_to_move:
                        try: shutil.move(src, dst)
                        except Exception: pass
                    profile_manager.reload_profiles()
                    if config_manager.get("runtime.default_persona") == h_name:
                        config_manager.set("runtime.default_persona", "samantha")
                        config_manager.save()

            # 9. WRITE_CANVAS
            elif tag == "WRITE_CANVAS" and "|" in inner:
                parts = inner.split("|", 1)
                target, content = parts[0].strip(), parts[1].strip()
                if target and content:
                    if target.startswith("#") or target.startswith("C0") or target.lower().startswith("slack:"):
                        badges.append(f"> 📋 **{name} published Slack Canvas to `{target.replace('slack:', '').strip()}`**")
                    else:
                        fname = target if target.endswith(".canvas") or target.endswith(".md") else f"{target}.canvas"
                        VaultManager.write_note(profile, fname, content)
                        rel_path = f"{vault_folder}/{fname}" if vault_folder else fname
                        badges.append(f"> 🎨 **{name} created Visual Canvas in Vault:** `{rel_path}`")

        # Fallback: If user explicitly asked to log/save to daily journal in the CURRENT turn and model forgot [DAILY_NOTE:] wrapper
        active_prompt = user_prompt.split("User Request:")[-1].strip() if "User Request:" in user_prompt else user_prompt.strip()
        if active_prompt and not has_daily_note_tag:
            if re.search(r"\b(?:log|save|write|record|create)\b[\s\S]*?\b(?:daily\s+(?:entry|note)|journal|diary)\b", active_prompt, re.I):
                reflection_candidate = ""
                if m_ref := re.search(r"(?:###?\s*(?:Reflection|Journal Entry|Daily Log)|---\s*\n(?:Journal Entry|Reflection))[\s\S]+", text, re.I):
                    reflection_candidate = m_ref.group(0).strip()
                elif re.search(r"\b(?:Entry:|Reflection:|Key Themes:|Discussion Summary:)", text, re.I):
                    cleaned_body = re.sub(r"^(?:Certainly|Sure|Of course|Here is|Here's)[^\n]*\n+", "", text.strip(), flags=re.I).strip()
                    if cleaned_body:
                        reflection_candidate = cleaned_body

                if reflection_candidate:
                    # Strip conversational sign-offs and pleasantries from the note payload
                    clean_payload = re.sub(r"(?:\n+\s*---\s*)?\n+(?:(?:Feel free|Let me know|I hope|Hope this|This journal entry|Please let me|If you need)[^\n]*)+[\s\S]*$", "", reflection_candidate, flags=re.I).strip()
                    if clean_payload:
                        VaultManager.write_daily_note(profile, clean_payload)
                        badges.append(f"> 📅 **{name} logged entry to Daily Notes**")

        clean_text = re.sub(r"```[a-zA-Z0-9_-]*\s*```\n?", "", clean_text)
        clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()
        return clean_text, badges
