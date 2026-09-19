"""
CREATE_PERSONA / DELETE_PERSONA tag handlers for `ActionProcessor`
(ADR-137, split out of actions.py).
"""

import logging
import os
import re
import shutil
from typing import TYPE_CHECKING

from sympose.config import config_manager

if TYPE_CHECKING:
    from sympose.actions_context import _ActionContext

log = logging.getLogger(__name__)


class PersonaActionMixin:
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

    @classmethod
    def _handle_create_persona(cls, ctx: "_ActionContext", inner: str) -> str:
        h_name, raw_yaml = cls._parse_persona_manifest(inner)
        if not (h_name and raw_yaml):
            ctx.badges.append(
                "> ⚠️ **Malformed `[CREATE_PERSONA]` action tag — ignored:** could not determine a handle from the provided YAML."
            )
            return ""

        p_dir = getattr(ctx.profile_manager, "profiles_dir", "profiles")
        os.makedirs(p_dir, exist_ok=True)
        yaml_file = os.path.join(p_dir, f"{h_name}.yaml")
        try:
            soul_content, manifest_yaml = cls._split_soul_content(raw_yaml)
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
            ctx.fire_action("CREATE_PERSONA", f"@{h_name}")
        except Exception as e:
            ctx.badges.append(f"> ⚠️ **Error creating persona `@{h_name}`:** {e}")
        return ""

    # --- 8. DELETE_PERSONA ---------------------------------------------------------
    @staticmethod
    def _handle_delete_persona(ctx: "_ActionContext", inner: str) -> str:
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
        ctx.fire_action("DELETE_PERSONA", f"@{h_name}")
        return ""
