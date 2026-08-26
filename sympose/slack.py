"""
🏛️ Sympose: Slack Socket Mode Daemon
Multi-agent concurrent router, thread context fetcher & event dispatcher.
"""

import os, re, sys, logging, threading
from typing import Dict, List, Tuple, Any, Optional

try: from slack_bolt import App; from slack_bolt.adapter.socket_mode import SocketModeHandler
except ImportError: App, SocketModeHandler = None, None

from sympose.engine import PersonaEngine
from sympose.actions import ActionProcessor
from sympose.config import convert_md_to_slack_mrkdwn


class SlackDaemon:
    """Slack Socket Mode integration with thread-isolated sessions and human-readable context."""

    user_cache: Dict[str, str] = {}
    name_to_id: Dict[str, str] = {}

    def __init__(self, engine: PersonaEngine, default_persona: Optional[str] = None, bot_token: Optional[str] = None, app_token: Optional[str] = None):
        self.engine, self.pm, self.config = engine, engine.pm, engine.config
        self.default_persona = default_persona or self.config.get("runtime.default_persona", "samantha").lower()
        p = f"SLACK_{self.default_persona.upper()}_"
        self.bot_token = (bot_token or os.getenv(f"{p}BOT_TOKEN") or os.getenv("SLACK_BOT_TOKEN", "")).strip()
        self.app_token = (app_token or os.getenv(f"{p}APP_TOKEN") or os.getenv("SLACK_APP_TOKEN", "")).strip()
        self.thread_personas, self.thread_histories, self.app, self.handler = {}, {}, None, None
        self.bot_user_id, self.bot_id = "", ""
        u_card = self.pm._read_file_safe(os.path.join(getattr(self.pm, "profiles_dir", "profiles"), "user_profile.md"))
        m = re.search(r"(?:Primary\s+User|User|Name):\s*([a-zA-Z0-9_\-]+)", u_card, re.I)
        self.primary_user = m.group(1).strip() if m else (os.getenv("USER") or "User")

    def _validate_tokens(self) -> bool:
        if not self.bot_token or not self.app_token or App is None or SocketModeHandler is None:
            if App is None: print("⚠️ [Sympose Slack] slack-bolt not installed.", file=sys.stderr)
            return False
        return True

    def _resolve_user_name(self, client: Any, user_id: str) -> str:
        if not user_id or not user_id.startswith("U"): return user_id or "Participant"
        if user_id in self.user_cache: return self.user_cache[user_id]
        try:
            u_info = client.users_info(user=user_id).get("user", {})
            name = u_info.get("profile", {}).get("display_name") or u_info.get("real_name") or u_info.get("name")
            if name:
                self.user_cache[user_id] = name
                self.name_to_id[name.lower()] = user_id
                self.name_to_id[u_info.get("name", "").lower()] = user_id
                return name
        except Exception: pass
        self.user_cache[user_id] = self.primary_user
        self.name_to_id[self.primary_user.lower()] = user_id
        return self.primary_user

    def _clean_mentions(self, client: Any, text: str) -> str:
        return re.sub(r"<@([A-Z0-9]+)>", lambda m: f"@{self._resolve_user_name(client, m.group(1))}", text)

    def _format_outgoing_mentions(self, text: str) -> str:
        return re.sub(r"@([a-zA-Z0-9_\-]+)", lambda m: f"<@{self.name_to_id[m.group(1).lower()]}>" if m.group(1).lower() in self.name_to_id else m.group(0), text)

    def _resolve_persona_and_prompt(self, text: str, thread_id: str) -> Tuple[str, str]:
        cleaned, personas = re.sub(r"<@[A-Z0-9]+>", "", text).strip(), self.pm.list_personas()
        alias_map: Dict[str, str] = {}
        for p in personas:
            h = p["handle"].lower()
            alias_map[h] = h
            for part in p.get("name", "").lower().split():
                if len(part) >= 3: alias_map[part] = h
            for al in p.get("aliases", []): alias_map[str(al).lower()] = h

        gm = re.match(r"^(?:hi|hey|hello|good\s+morning|morning|good\s+afternoon|good\s+evening)\s+@?([a-zA-Z0-9_\-]+)[,:\s]*(.*)$", cleaned, re.I | re.DOTALL)
        if gm and gm.group(1).lower() in alias_map:
            t = alias_map[gm.group(1).lower()]; self.thread_personas[thread_id] = t; return t, (gm.group(2).strip() or cleaned)

        m = re.match(r"^@?([a-zA-Z0-9_\-]+)[:,\s]+(.*)$", cleaned, re.DOTALL)
        if m and m.group(1).lower() in alias_map:
            t = alias_map[m.group(1).lower()]; self.thread_personas[thread_id] = t; return t, m.group(2).strip()

        if cleaned.startswith("/switch"):
            parts = cleaned.split()
            if len(parts) > 1 and parts[1].replace("@", "").lower() in alias_map:
                t = alias_map[parts[1].replace("@", "").lower()]; self.thread_personas[thread_id] = t; return t, f"Switched active persona to @{t}."

        active = self.thread_personas.get(thread_id, self.default_persona)
        return (active if active in [p["handle"].lower() for p in personas] else self.default_persona), cleaned

    def _fetch_slack_context(self, client: Any, channel_id: str, thread_ts: Optional[str], current_ts: str, prompt: str) -> str:
        """Retrieves Slack thread replies or recent channel history with human-readable usernames."""
        lines: List[str] = []
        if thread_ts:
            try:
                res = client.conversations_replies(channel=channel_id, ts=thread_ts, limit=int(self.config.get("performance.slack_thread_context_limit", 12)))
                lines = [f"- {self._resolve_user_name(client, m.get('user') or m.get('username') or '')}: {self._clean_mentions(client, m.get('text', '').strip())}" for m in res.get("messages", []) if m.get("ts") != current_ts and m.get("text", "").strip()]
                if lines: return "### Slack Thread Context (Preceding Messages in this Thread):\n" + "\n".join(lines)
            except Exception as e: logging.debug(f"Thread context: {e}")

        if re.search(r"\b(summarize|summary|catch\s*up|recap|what\s+happened|this\s+(?:thread|channel|conversation))\b", prompt, re.I):
            try:
                res = client.conversations_history(channel=channel_id, limit=25)
                for m in reversed(res.get("messages", [])):
                    if m.get("ts") != current_ts and m.get("text", "").strip():
                        lines.append(f"- {self._resolve_user_name(client, m.get('user') or m.get('username') or '')}: {self._clean_mentions(client, m.get('text', '').strip())}")
                if lines: return "### Recent Slack Channel History:\n" + "\n".join(lines)
            except Exception as e: logging.debug(f"Channel context: {e}")
        return ""

    def _process_message(self, client: Any, event: Dict[str, Any], say: Any) -> None:
        channel_id, msg_ts, raw_text = event.get("channel", ""), event.get("ts", ""), event.get("text", "")
        if not raw_text.strip(): return
        if (getattr(self, "bot_user_id", "") and event.get("user") == self.bot_user_id) or (getattr(self, "bot_id", "") and event.get("bot_id") == self.bot_id): return

        is_dm = (event.get("channel_type") == "im")
        thread_ts = event.get("thread_ts") if is_dm else (event.get("thread_ts") or event.get("ts", ""))
        thread_id = f"{channel_id}:{event.get('thread_ts') or event.get('ts') or channel_id}"

        handle, prompt = self._resolve_persona_and_prompt(raw_text, thread_id)
        if bool(os.getenv(f"SLACK_{handle.upper()}_BOT_TOKEN")) and handle != self.default_persona: return

        profile = self.pm.get_profile(handle)
        name = profile.get("name", handle) if profile else handle
        slack_ctx = self._fetch_slack_context(client, channel_id, event.get("thread_ts"), msg_ts, prompt)
        full_prompt = f"{slack_ctx}\n\nUser Request: {prompt}" if slack_ctx else prompt

        print(f"📥 [Slack Event] @{handle} ({name}) handling message: {prompt[:60]}")
        try: client.reactions_add(channel=channel_id, timestamp=msg_ts, name="eyes")
        except Exception: pass

        th_key = f"{thread_id}:{handle}"
        if bool(re.search(r"^(?:please\s+)?(?:delete|clear|wipe|erase|purge)\s+(?:our\s+|the\s+|this\s+)?(?:thread|chat|conversation|history|messages?)$", prompt.strip(), re.I)) or prompt.strip() in ("/clear", "/delete", "/wipe", "/reset"):
            self.thread_histories.pop(th_key, None); self.engine.reset_history(handle); deleted = 0
            if event.get("thread_ts"):
                try:
                    for m in client.conversations_replies(channel=channel_id, ts=event.get("thread_ts"), limit=100).get("messages", []):
                        try: client.chat_delete(channel=channel_id, ts=m.get("ts")); deleted += 1
                        except Exception: pass
                except Exception: pass
            if deleted == 0: say(text=f"🧹 Conversation history deleted for @{handle}.", thread_ts=thread_ts)
            return

        self.engine.histories[handle] = self.thread_histories.get(th_key, [])
        try:
            chunks = [c for c in self.engine.chat_stream(handle, full_prompt) if c != "CLEARED_SESSION"]
            self.thread_histories[th_key] = self.engine.get_history(handle)
            raw_text = "".join(chunks).strip()
            reacts = [m.group(1).strip().strip(":") for m in re.finditer(r"\[(?:ACTION:)?REACT:\s*([a-zA-Z0-9_\-+:]+?)\]", raw_text, re.I)] or ["white_check_mark"]
            clean_text, badges = ActionProcessor.execute_actions(self.pm, handle, raw_text)
            if badges: clean_text = (clean_text + "\n\n" + "\n".join(badges)).strip()
            say(text=self._format_outgoing_mentions(convert_md_to_slack_mrkdwn(clean_text or f"*{name} acknowledged your message.*")), thread_ts=thread_ts)
            try: client.reactions_remove(channel=channel_id, timestamp=msg_ts, name="eyes")
            except Exception: pass
            for em in reacts:
                try: client.reactions_add(channel=channel_id, timestamp=msg_ts, name=em)
                except Exception: pass
        except Exception as e:
            print(f"⚠️ [Slack Error] @{handle}: {e}", file=sys.stderr); say(text=f"⚠️ *{name} encountered an error:* `{e}`", thread_ts=thread_ts)

    def setup(self) -> bool:
        if not self._validate_tokens(): return False
        try:
            self.app = App(token=self.bot_token)
            auth = self.app.client.auth_test()
            self.bot_user_id, self.bot_id = auth.get("user_id", ""), auth.get("bot_id", "")
            self.name_to_id[self.default_persona] = self.bot_user_id
            try:
                for u in self.app.client.users_list().get("members", []):
                    for k in [u.get("name"), u.get("real_name"), u.get("profile", {}).get("display_name")]:
                        if k and u.get("id"): self.name_to_id[k.lower()] = u.get("id")
            except Exception: pass
            self.app.event("app_mention")(lambda client, event, say: self._process_message(client, event, say))
            self.app.event("message")(lambda client, event, say: self._process_message(client, event, say) if (event.get("channel_type") == "im" or event.get("thread_ts")) else None)
            self.handler = SocketModeHandler(self.app, self.app_token); return True
        except Exception as e:
            print(f"⚠️ [Sympose Slack] Failed to start @{self.default_persona}: {e}", file=sys.stderr); return False

    def start(self) -> None:
        while True:
            try:
                if self.setup() and self.handler: print(f"⚡ [Sympose] Slack Bot active for @{self.default_persona}"); self.handler.start()
            except Exception as e: print(f"⚠️ [Slack Reconnect] @{self.default_persona}: {e}. Retrying in 3s...", file=sys.stderr); import time; time.sleep(3)


class MultiAgentSlackRunner:
    """Discovers and runs all configured persona Slack bots concurrently."""

    @classmethod
    def run_all(cls, engine: PersonaEngine, persona_override: Optional[str] = None) -> None:
        daemons = [d for h in ([persona_override.lower()] if persona_override else [p["handle"].lower() for p in engine.pm.list_personas()]) if (d := SlackDaemon(engine, default_persona=h))._validate_tokens() and d.setup()]
        if not daemons: sys.exit("⚠️ [Sympose Slack] Missing or invalid Slack tokens in .env.")
        print(f"🚀 [Sympose] Launching {len(daemons)} Slack Agent(s)...")
        threads = [threading.Thread(target=d.start, daemon=True) for d in daemons]
        for t in threads: t.start()
        try:
            for t in threads: t.join()
        except (KeyboardInterrupt, SystemExit): pass
