"""
Vault note/canvas tag handlers for `ActionProcessor` (ADR-137, split out of
actions.py): WRITE_NOTE, APPEND_NOTE, DAILY_NOTE, READ_NOTE/VIEW_NOTE,
WRITE_CANVAS.
"""

from typing import TYPE_CHECKING

from sympose.config import config_manager
from sympose.vault import VaultManager
from sympose.wiki_lint_support import wiki_lint_write_gate

if TYPE_CHECKING:
    from sympose.actions_context import _ActionContext


def _rel_note_path(ctx: "_ActionContext", filename: str) -> str:
    rel_path = f"{ctx.vault_folder}/{filename}" if ctx.vault_folder else filename
    if not rel_path.endswith(".md"):
        rel_path += ".md"
    return rel_path


def _wiki_lint_gate(ctx: "_ActionContext", rel_path: str) -> str | None:
    """ADR-134's structural gap, closed: a code-level backstop for a
    lint-only persona (`wiki_lint` without `wiki_ingest`) whose
    `lint_auto_fix` is off, so a WRITE_NOTE/APPEND_NOTE into `wiki.root`
    doesn't depend solely on the model obeying its own prompt-level mode."""
    return wiki_lint_write_gate(
        skills=ctx.profile.get("skills") or [],
        lint_auto_fix=bool(ctx.profile.get("lint_auto_fix", False)),
        wiki_root=str(config_manager.get("wiki.root") or ""),
        log_file=str(config_manager.get("wiki.log_file") or "log.md"),
        rel_path=rel_path,
    )


class NotesActionMixin:
    # --- 1. WRITE_NOTE / 2. APPEND_NOTE -------------------------------------
    # classmethods (not staticmethods) purely so `cls._op_failed(...)` can
    # reach ParsingMixin's method through ActionProcessor's MRO — the same
    # cross-mixin pattern `_handle_spawn_sub_agent` already relies on for
    # `cls.execute_actions`.
    @classmethod
    def _handle_write_note(cls, ctx: "_ActionContext", inner: str) -> str:
        parts = inner.split("|", 1)
        filename, content = parts[0].strip(), parts[1].strip()
        if filename and content:
            rel_path = _rel_note_path(ctx, filename)
            result = _wiki_lint_gate(ctx, rel_path) or VaultManager.write_note(
                ctx.profile, filename, content
            )
            if cls._op_failed(result):
                ctx.badges.append(f"> ⚠️ **{ctx.name} could not save note:** {result}")
            else:
                ctx.badges.append(f"> 📝 **{ctx.name} saved note to Vault:** `{rel_path}`")
                ctx.fire_action("WRITE_NOTE", rel_path)
        return ""

    @classmethod
    def _handle_append_note(cls, ctx: "_ActionContext", inner: str) -> str:
        parts = inner.split("|", 1)
        filename, content = parts[0].strip(), parts[1].strip()
        if filename and content:
            rel_path = _rel_note_path(ctx, filename)
            result = _wiki_lint_gate(ctx, rel_path) or VaultManager.append_note(
                ctx.profile, filename, content
            )
            if cls._op_failed(result):
                ctx.badges.append(
                    f"> ⚠️ **{ctx.name} could not append to note:** {result}"
                )
            else:
                ctx.badges.append(
                    f"> 📝 **{ctx.name} appended to Vault note:** `{rel_path}`"
                )
                ctx.fire_action("APPEND_NOTE", rel_path)
        return ""

    # --- 3. DAILY_NOTE -------------------------------------------------------
    @classmethod
    def _handle_daily_note(cls, ctx: "_ActionContext", inner: str) -> str:
        result = VaultManager.write_daily_note(ctx.profile, inner)
        if cls._op_failed(result):
            ctx.badges.append(f"> ⚠️ **{ctx.name} could not log daily entry:** {result}")
        else:
            ctx.badges.append(f"> 📅 **{ctx.name} logged entry to Daily Notes**")
            ctx.fire_action("DAILY_NOTE", "")
        return ""

    # --- 4b. READ_NOTE / VIEW_NOTE ---------------------------------------------
    @staticmethod
    def _handle_read_note(ctx: "_ActionContext", inner: str) -> str:
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

    # --- WRITE_CANVAS -----------------------------------------------------------
    @classmethod
    def _handle_write_canvas(cls, ctx: "_ActionContext", inner: str) -> str:
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
        if cls._op_failed(result):
            ctx.badges.append(f"> ⚠️ **{ctx.name} could not save Visual Canvas:** {result}")
        else:
            rel_path = f"{ctx.vault_folder}/{fname}" if ctx.vault_folder else fname
            ctx.badges.append(
                f"> 🎨 **{ctx.name} created Visual Canvas in Vault:** `{rel_path}`"
            )
        return ""
