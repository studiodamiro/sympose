"""
🏛️ Sympose: Slack Socket Mode Daemon
Multi-agent concurrent router, thread context fetcher & event dispatcher.
"""

import os, re, sys, time, logging, threading
from typing import Dict, List, Tuple, Any, Optional, Set

try: from slack_bolt import App; from slack_bolt.adapter.socket_mode import SocketModeHandler
except ImportError: App, SocketModeHandler = None, None

from sympose.engine import PersonaEngine
from sympose.actions import ActionProcessor
from sympose.config import convert_md_to_slack_mrkdwn


class SlackDaemon:
    """Slack Socket Mode integration with thread-isolated sessions and human-readable context."""
    user_cache: Dict[str, str] = {}
    name_to_id: Dict[str, str] = {}
    bot_user_ids: Set[str] = set()

    def __init__(self, engine: PersonaEngine, default_persona: Optional[str] = None, bot_token: Optional[str] = None, app_token: Optional[str] = None):
        self.engine, self.pm, self.config = engine, engine.pm, engine.config
        self.default_persona = default_persona or self.config.get("runtime.default_persona", "samantha").lower()
        p = f"SLACK_{self.default_persona.upper()}_"
        self.bot_token = (bot_token or os.getenv(f"{p}BOT_TOKEN") or (os.getenv("SLACK_AURELIUS_BOT_TOKEN") if self.default_persona == "archia" else None) or os.getenv("SLACK_BOT_TOKEN", "")).strip()
        self.app_token = (app_token or os.getenv(f"{p}APP_TOKEN") or (os.getenv("SLACK_AURELIUS_APP_TOKEN") if self.default_persona == "archia" else None) or os.getenv("SLACK_APP_TOKEN", "")).strip()
        self.thread_personas, self.thread_histories, self.app, self.handler, self.bot_user_id, self.bot_id, self.boot_ts = {}, {}, None, None, "", "", time.time()
        self._is_setup = False
        u_card = self.pm._read_file_safe(os.path.join(getattr(self.pm, "profiles_dir", "profiles"), "user_profile.md"))
        m = re.search(r"[-*]?\s*(?:\*\*|__)?(?:Primary\s+User|User|Name)(?:\*\*|__)?\s*:\s*([^\n\r]+)", u_card, re.I)
        self.primary_user = m.group(1).strip().strip("*_`") if m and m.group(1).strip() else (os.getenv("USER") or "User")

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

    def _clean_mentions(self, client: Any, text: str) -> str: return re.sub(r"<@([A-Z0-9]+)>", lambda m: f"@{self._resolve_user_name(client, m.group(1))}", text)
    def _format_outgoing_mentions(self, text: str) -> str:
        def replace_tag(m):
            tag = m.group(1).lower()
            if tag in self.name_to_id: return f"<@{self.name_to_id[tag]}>"
            if tag in ("user", "human", "primary_user") and self.primary_user.lower() in self.name_to_id:
                return f"<@{self.name_to_id[self.primary_user.lower()]}>"
            return m.group(0)
        return re.sub(r"@([a-zA-Z0-9_\-]+)", replace_tag, text)

    def _resolve_persona_and_prompt(self, text: str, thread_id: str) -> Tuple[str, str]:
        cleaned, personas = re.sub(r"<@[A-Z0-9]+>", "", text).strip(), self.pm.list_personas()
        alias_map = {p["handle"].lower(): p["handle"].lower() for p in personas}
        for p in personas:
            h = p["handle"].lower()
            for part in p.get("name", "").lower().split():
                if len(part) >= 3: alias_map[part] = h
            for al in p.get("aliases", []): alias_map[str(al).lower()] = h

        gm = re.match(r"^(?:hi|hey|hello|good\s+morning|morning|good\s+afternoon|good\s+evening)\s+@?([a-zA-Z0-9_\-]+)[,:\s]*(.*)$", cleaned, re.I | re.DOTALL)
        if gm and gm.group(1).lower() in alias_map:
            t = alias_map[gm.group(1).lower()]; self.thread_personas[thread_id] = t; return t, (gm.group(2).strip() or cleaned)

        m = re.match(r"^@?([a-zA-Z0-9_\-]+)[:,\s]+(.*)$", cleaned, re.DOTALL)
        if m and m.group(1).lower() in alias_map:
            t = alias_map[m.group(1).lower()]; self.thread_personas[thread_id] = t; return t, m.group(2).strip()

        if cleaned.startswith("/switch") and len(parts := cleaned.split()) > 1 and parts[1].replace("@", "").lower() in alias_map:
            t = alias_map[parts[1].replace("@", "").lower()]; self.thread_personas[thread_id] = t; return t, f"Switched active persona to @{t}."

        active = self.thread_personas.get(thread_id, self.default_persona)
        return (active if active in [p["handle"].lower() for p in personas] else self.default_persona), cleaned

    def _fetch_slack_context(self, client: Any, channel_id: str, thread_ts: Optional[str], current_ts: str, prompt: str) -> str:
        """Retrieves Slack thread replies or recent channel history with human-readable usernames."""
        if thread_ts:
            try:
                res = client.conversations_replies(channel=channel_id, ts=thread_ts, limit=int(self.config.get("performance.slack_thread_context_limit", 12)))
                if tl := [f"- {self._resolve_user_name(client, m.get('user') or m.get('username') or '')}: {self._clean_mentions(client, m.get('text', '').strip())}" for m in res.get("messages", []) if m.get("ts") != current_ts and m.get("text", "").strip()]:
                    return "### Slack Thread Context (Preceding Messages in this Thread):\n" + "\n".join(tl)
            except Exception as e: logging.debug(f"Thread context: {e}")

        if re.search(r"\b(summarize|summary|catch\s*up|recap|what\s+happened|this\s+(?:thread|channel|conversation))\b", prompt, re.I):
            try:
                cl = [f"- {self._resolve_user_name(client, m.get('user') or m.get('username') or '')}: {self._clean_mentions(client, m.get('text', '').strip())}" for m in reversed(client.conversations_history(channel=channel_id, limit=25).get("messages", [])) if m.get("ts") != current_ts and m.get("text", "").strip()]
                if cl: return "### Recent Slack Channel History:\n" + "\n".join(cl)
            except Exception as e: logging.debug(f"Channel context: {e}")
        return ""

    def _process_message(self, client: Any, event: Dict[str, Any], say: Any) -> None:
        channel_id, msg_ts, raw_text = event.get("channel", ""), event.get("ts", ""), event.get("text", "")
        if not raw_text.strip() or float(msg_ts or 0) < (getattr(self, "boot_ts", 0) - 5.0): return
        sender = event.get("user") or ""
        sender_bot = event.get("bot_id") or ""
        if (getattr(self, "bot_user_id", "") and sender == self.bot_user_id) or (getattr(self, "bot_id", "") and sender_bot == self.bot_id): return

        is_dm = (event.get("channel_type") == "im")
        thread_ts = event.get("thread_ts") if is_dm else (event.get("thread_ts") or event.get("ts", ""))
        thread_id = f"{channel_id}:{event.get('thread_ts') or event.get('ts') or channel_id}"

        handle, prompt = self._resolve_persona_and_prompt(raw_text, thread_id)
        if bool(os.getenv(f"SLACK_{handle.upper()}_BOT_TOKEN")) and handle != self.default_persona: return

        if bool(sender_bot or sender in self.bot_user_ids or event.get("subtype") == "bot_message") and event.get("thread_ts"):
            try:
                msgs = client.conversations_replies(channel=channel_id, ts=event.get("thread_ts"), limit=8).get("messages", [])
                streak = sum(1 for m in reversed(msgs) if (m.get("bot_id") or m.get("user") in self.bot_user_ids or m.get("subtype") == "bot_message"))
                if streak >= int(self.config.get("performance.max_consecutive_bot_turns", 3)):
                    prompt += "\n\n[SYSTEM: Discussion turn limit reached. Deliver concluding summary for the user without tagging other bots.]"
            except Exception: pass

        name = self.pm.get_profile(handle).get("name", handle) if self.pm.get_profile(handle) else handle
        slack_ctx = self._fetch_slack_context(client, channel_id, event.get("thread_ts"), msg_ts, prompt)
        full_prompt = f"{slack_ctx}\n\nUser Request: {prompt}" if slack_ctx else prompt

        print(f"📥 [Slack Event] @{handle} ({name}) handling message: {prompt[:60]}")
        try: client.reactions_add(channel=channel_id, timestamp=msg_ts, name="eyes")
        except Exception: pass

        th_key = f"{thread_id}:{handle}"
        if bool(re.search(r"\b(?:delete|clear|wipe|erase|purge|reset)\s+(?:our\s+|the\s+|this\s+)?(?:thread|chat|conversation|history|session|context|messages?)", prompt, re.I)) or prompt.strip() in ("/clear", "/delete", "/wipe", "/reset"):
            self.thread_histories.pop(th_key, None); self.engine.reset_history(handle, session_id=th_key)
            if event.get("thread_ts"):
                try:
                    for m in client.conversations_replies(channel=channel_id, ts=event.get("thread_ts"), limit=100).get("messages", []):
                        try: client.chat_delete(channel=channel_id, ts=m.get("ts"))
                        except Exception: pass
                except Exception: pass
            try: client.reactions_remove(channel=channel_id, timestamp=msg_ts, name="eyes"); client.reactions_add(channel=channel_id, timestamp=msg_ts, name="broom")
            except Exception: pass
            if not re.search(r"\b(?:do\s*not\s*reply|no\s*reply|do\s*not\s*acknowledge|no\s*response|silent|silence)\b", prompt, re.I): say(text=f"🧹 Conversation history deleted for @{handle}.", thread_ts=thread_ts)
            return

        try:
            chunks = [c for c in self.engine.chat_stream(handle, full_prompt, session_id=th_key) if c != "CLEARED_SESSION"]
            self.thread_histories[th_key] = self.engine.get_history(handle, session_id=th_key)
            raw_text = "".join(chunks).strip()
            clean_text, badges = ActionProcessor.execute_actions(self.pm, handle, raw_text)
            if badges: clean_text = (clean_text + "\n\n" + "\n".join(badges)).strip()
            is_silent = not clean_text or clean_text.strip().lower() in ("(no response)", "no response", "(silence)", "...", "no response.")
            if not is_silent: say(text=self._format_outgoing_mentions(convert_md_to_slack_mrkdwn(clean_text)), thread_ts=thread_ts)
            try: client.reactions_remove(channel=channel_id, timestamp=msg_ts, name="eyes")
            except Exception: pass
            for em in ([m.group(1).strip().strip(":") for m in re.finditer(r"\[(?:ACTION:)?REACT:\s*([a-zA-Z0-9_\-+:]+?)\]", raw_text, re.I)] or (["white_check_mark"] if is_silent else [])):
                try: client.reactions_add(channel=channel_id, timestamp=msg_ts, name=em)
                except Exception: pass
        except Exception as e:
            print(f"⚠️ [Slack Error] @{handle}: {e}", file=sys.stderr); say(text=f"⚠️ *{name} encountered an error:* `{e}`", thread_ts=thread_ts)

    def setup(self) -> bool:
        if self._is_setup and self.handler:
            return True
        if not self._validate_tokens(): return False
        try:
            self.app = App(token=self.bot_token)
            auth = self.app.client.auth_test()
            self.bot_user_id, self.bot_id = auth.get("user_id", ""), auth.get("bot_id", "")
            self.bot_user_ids.add(self.bot_user_id); self.name_to_id[self.default_persona] = self.bot_user_id
            try:
                for u in self.app.client.users_list().get("members", []):
                    if u.get("is_bot") and u.get("id"): self.bot_user_ids.add(u["id"])
                    for k in [u.get("name"), u.get("real_name"), u.get("profile", {}).get("display_name")]: (self.name_to_id.update({k.lower(): u["id"]}) if k and u.get("id") else None)
            except Exception: pass
            self.app.event("app_mention")(lambda client, event, say: self._process_message(client, event, say))
            self.app.event("message")(lambda client, event, say: self._process_message(client, event, say) if (event.get("channel_type") == "im" or event.get("thread_ts")) else None)
            self.handler = SocketModeHandler(self.app, self.app_token)
            self._is_setup = True
            return True
        except Exception as e:
            print(f"⚠️ [Sympose Slack] Failed to start @{self.default_persona}: {e}", file=sys.stderr); return False

    def start(self) -> None:
        while True:
            try:
                if self.setup() and self.handler: print(f"⚡ [Sympose] Slack Bot active for @{self.default_persona}"); self.handler.start()
            except Exception as e:
                self._is_setup = False
                print(f"⚠️ [Slack Reconnect] @{self.default_persona}: {e}. Retrying in 3s...", file=sys.stderr)
                import time; time.sleep(3)


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
