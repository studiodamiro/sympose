"""
🏛️ Sympose: Slack Socket Mode Daemon
Multi-agent concurrent router, thread context fetcher & event dispatcher.
"""

import os, re, sys, logging, threading
from typing import Dict, List, Tuple, Any, Optional

try: from slack_bolt import App; from slack_bolt.adapter.socket_mode import SocketModeHandler
except ImportError: App, SocketModeHandler = None, None

from sympose.engine import PersonaEngine
from sympose.config import convert_md_to_slack_mrkdwn


class SlackDaemon:
    """Slack Socket Mode integration with thread-isolated sessions and human-readable context."""

    user_cache: Dict[str, str] = {}

    def __init__(self, engine: PersonaEngine, default_persona: Optional[str] = None, bot_token: Optional[str] = None, app_token: Optional[str] = None):
        self.engine, self.pm, self.config = engine, engine.pm, engine.config
        self.default_persona = default_persona or self.config.get("runtime.default_persona", "samantha").lower()
        p_prefix = f"SLACK_{self.default_persona.upper()}_"
        self.bot_token = (bot_token or os.getenv(f"{p_prefix}BOT_TOKEN") or os.getenv("SLACK_BOT_TOKEN", "")).strip()
        self.app_token = (app_token or os.getenv(f"{p_prefix}APP_TOKEN") or os.getenv("SLACK_APP_TOKEN", "")).strip()
        self.thread_personas: Dict[str, str] = {}
        self.thread_histories: Dict[str, List[Dict[str, str]]] = {}
        self.app, self.handler = None, None
        u_card = self.pm._read_file_safe(os.path.join(getattr(self.pm, "profiles_dir", "profiles"), "user_profile.md"))
        m = re.search(r"Primary User:\s*([a-zA-Z0-9_\-]+)", u_card, re.I)
        self.primary_user = m.group(1).strip() if m else "damiro"

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
                return name
        except Exception: pass
        self.user_cache[user_id] = self.primary_user
        return self.primary_user

    def _clean_mentions(self, client: Any, text: str) -> str:
        return re.sub(r"<@([A-Z0-9]+)>", lambda m: f"@{self._resolve_user_name(client, m.group(1))}", text)

    def _resolve_persona_and_prompt(self, text: str, thread_id: str) -> Tuple[str, str]:
        cleaned = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
        personas = self.pm.list_personas()
        alias_map = {"mauri": "aurelius", "marcus": "aurelius", "sam": "samantha"}
        for p in personas:
            h = p["handle"].lower()
            alias_map[h] = h
            for part in p.get("name", "").lower().split():
                if len(part) >= 3: alias_map[part] = h
            for al in p.get("aliases", []): alias_map[str(al).lower()] = h

        match = re.match(r"^@?([a-zA-Z0-9_\-]+)[:,\s]+(.*)$", cleaned, re.DOTALL)
        if match and match.group(1).lower() in alias_map:
            target = alias_map[match.group(1).lower()]
            self.thread_personas[thread_id] = target
            return target, match.group(2).strip()

        if cleaned.startswith("/switch"):
            parts = cleaned.split()
            if len(parts) > 1 and parts[1].replace("@", "").lower() in alias_map:
                target = alias_map[parts[1].replace("@", "").lower()]
                self.thread_personas[thread_id] = target
                return target, f"Switched active persona to @{target}."

        active = self.thread_personas.get(thread_id, self.default_persona)
        return (active if active in [p["handle"].lower() for p in personas] else self.default_persona), cleaned

    def _fetch_slack_context(self, client: Any, channel_id: str, thread_ts: Optional[str], current_ts: str, prompt: str) -> str:
        """Retrieves Slack thread replies or recent channel history with human-readable usernames."""
        lines: List[str] = []
        if thread_ts:
            try:
                res = client.conversations_replies(channel=channel_id, ts=thread_ts, limit=50)
                for m in res.get("messages", []):
                    if m.get("ts") != current_ts and m.get("text", "").strip():
                        lines.append(f"- {self._resolve_user_name(client, m.get('user') or m.get('username') or '')}: {self._clean_mentions(client, m.get('text', '').strip())}")
                if lines:
                    return "### Slack Thread Context (Preceding Messages in this Thread):\n" + "\n".join(lines)
            except Exception as e:
                logging.debug(f"Thread context: {e}")

        if re.search(r"\b(summarize|summary|catch\s*up|recap|what\s+happened|this\s+(?:thread|channel|conversation))\b", prompt, re.I):
            try:
                res = client.conversations_history(channel=channel_id, limit=25)
                for m in reversed(res.get("messages", [])):
                    if m.get("ts") != current_ts and m.get("text", "").strip():
                        lines.append(f"- {self._resolve_user_name(client, m.get('user') or m.get('username') or '')}: {self._clean_mentions(client, m.get('text', '').strip())}")
                if lines:
                    return "### Recent Slack Channel History:\n" + "\n".join(lines)
            except Exception as e:
                logging.debug(f"Channel context: {e}")
        return ""

    def _process_message(self, client: Any, event: Dict[str, Any], say: Any) -> None:
        channel_id, thread_ts = event.get("channel", ""), event.get("thread_ts") or event.get("ts", "")
        msg_ts, raw_text = event.get("ts", ""), event.get("text", "")
        thread_id = f"{channel_id}:{thread_ts}"
        if not raw_text.strip() or event.get("bot_id") or event.get("subtype") == "bot_message":
            return

        handle, prompt = self._resolve_persona_and_prompt(raw_text, thread_id)
        profile = self.pm.get_profile(handle)
        name = profile.get("name", handle) if profile else handle
        slack_ctx = self._fetch_slack_context(client, channel_id, event.get("thread_ts"), msg_ts, prompt)
        full_prompt = f"{slack_ctx}\n\nUser Request: {prompt}" if slack_ctx else prompt

        print(f"📥 [Slack Event] @{handle} ({name}) handling message: {prompt[:60]}")
        try: client.reactions_add(channel=channel_id, timestamp=msg_ts, name="eyes")
        except Exception: pass

        th_key = f"{thread_id}:{handle}"
        # Direct Slack Thread Deletion & In-Memory Reset
        if bool(re.search(r"^(?:please\s+)?(?:delete|clear|wipe|erase|purge)\s+(?:our\s+|the\s+|this\s+)?(?:thread|chat|conversation|history|messages?)$", prompt.strip(), re.I)) or prompt.strip() in ("/clear", "/delete", "/wipe", "/reset"):
            self.thread_histories.pop(th_key, None)
            self.engine.reset_history(handle)
            deleted = 0
            if event.get("thread_ts"):
                try:
                    res = client.conversations_replies(channel=channel_id, ts=event.get("thread_ts"), limit=100)
                    for m in res.get("messages", []):
                        try: client.chat_delete(channel=channel_id, ts=m.get("ts")); deleted += 1
                        except Exception: pass
                except Exception: pass
            if deleted == 0: say(text=f"🧹 Conversation history deleted for @{handle}.", thread_ts=thread_ts)
            return

        self.engine.histories[handle] = self.thread_histories.get(th_key, [])
        try:
            chunks = [c for c in self.engine.chat_stream(handle, full_prompt) if c != "CLEARED_SESSION"]
            self.thread_histories[th_key] = self.engine.get_history(handle)
            say(text=convert_md_to_slack_mrkdwn("".join(chunks).strip()), thread_ts=thread_ts)
            try: client.reactions_remove(channel=channel_id, timestamp=msg_ts, name="eyes")
            except Exception: pass
            try: client.reactions_add(channel=channel_id, timestamp=msg_ts, name="white_check_mark")
            except Exception: pass
        except Exception as e:
            logging.error(f"Error handling Slack event: {e}")
            say(text=f"⚠️ *{name} encountered an error:* `{e}`", thread_ts=thread_ts)

    def setup(self) -> bool:
        if not self._validate_tokens(): return False
        try:
            self.app = App(token=self.bot_token)
            self.app.event("app_mention")(lambda client, event, say: self._process_message(client, event, say))
            self.app.event("message")(lambda client, event, say: self._process_message(client, event, say) if (event.get("channel_type") == "im" or event.get("thread_ts")) else None)
            self.handler = SocketModeHandler(self.app, self.app_token)
            return True
        except Exception as e:
            print(f"⚠️ [Sympose Slack] Failed to start @{self.default_persona}: {e}", file=sys.stderr)
            return False

    def start(self) -> None:
        if self.setup() and self.handler:
            print(f"⚡ [Sympose] Slack Bot active for @{self.default_persona}")
            self.handler.start()


class MultiAgentSlackRunner:
    """Discovers and runs all configured persona Slack bots concurrently."""

    @classmethod
    def run_all(cls, engine: PersonaEngine, persona_override: Optional[str] = None) -> None:
        daemons: List[SlackDaemon] = []
        handles = [persona_override.lower()] if persona_override else [p["handle"].lower() for p in engine.pm.list_personas()]
        for h in handles:
            d = SlackDaemon(engine, default_persona=h)
            if d._validate_tokens() and not any(x.bot_token == d.bot_token for x in daemons): daemons.append(d)

        if not daemons:
            d = SlackDaemon(engine)
            if d.setup(): daemons.append(d)
            else:
                print("⚠️ [Sympose Slack] Missing or invalid Slack tokens in .env.", file=sys.stderr)
                sys.exit(1)

        print(f"🚀 [Sympose] Launching {len(daemons)} Slack Agent(s)...")
        threads = [threading.Thread(target=d.handler.start, daemon=True) for d in daemons if d.setup() and d.handler]
        for t in threads: t.start()
        try:
            for t in threads: t.join()
        except (KeyboardInterrupt, SystemExit):
            print("\n🛑 [Sympose] All Slack Daemons terminated gracefully.")
