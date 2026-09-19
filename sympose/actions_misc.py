"""
REMEMBER / SEARCH / WEB_SEARCH / CONFIG_SET tag handlers for
`ActionProcessor` (ADR-137, split out of actions.py) — the handlers that
don't share a bigger theme with any other cluster.
"""

from typing import Any, TYPE_CHECKING

from sympose.config import config_manager
from sympose.native_tools import NativeTools

if TYPE_CHECKING:
    from sympose.actions_context import _ActionContext


class MiscActionMixin:
    # --- 4. REMEMBER -----------------------------------------------------------
    @staticmethod
    def _handle_remember(ctx: "_ActionContext", inner: str) -> str:
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

    # --- 5b. SEARCH / WEB_SEARCH (Direct in-turn live search) -------------------
    @staticmethod
    def _handle_search(ctx: "_ActionContext", inner: str) -> str:
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
            ctx.fire_action("SEARCH", query)
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

    @classmethod
    def _handle_config_set(cls, ctx: "_ActionContext", inner: str) -> str:
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
            val = cls._coerce_unknown_config_value(raw_val)

        config_manager.set(key, val)
        config_manager.save()
        ctx.badges.append(
            f"> ⚙️ **{ctx.name} updated runtime configuration:** `{key}` = `{val}`"
        )
        ctx.fire_action("CONFIG_SET", key)
        return ""
