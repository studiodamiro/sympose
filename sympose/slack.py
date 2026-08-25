"""
🏛️ Sympose: Slack Socket Mode Daemon
Multi-agent concurrent router & thread-isolated event dispatcher.
"""

import os
import re
import sys
import logging
import threading
from typing import Dict, List, Tuple, Any, Optional

try:
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
except ImportError:
    App = None
    SocketModeHandler = None

from sympose.engine import PersonaEngine
from sympose.config import convert_md_to_slack_mrkdwn


class SlackDaemon:
    """Slack Socket Mode integration for Sympose with thread-isolated multi-agent sessions."""

    def __init__(self, engine: PersonaEngine, default_persona: Optional[str] = None, bot_token: Optional[str] = None, app_token: Optional[str] = None):
        self.engine = engine
        self.pm = engine.pm
        self.config = engine.config
        self.default_persona = default_persona or self.config.get("runtime.default_persona", "samantha").lower()
        
        # Resolve persona-specific or universal tokens
        p_prefix = f"SLACK_{self.default_persona.upper()}_"
        self.bot_token = (bot_token or os.getenv(f"{p_prefix}BOT_TOKEN") or os.getenv("SLACK_BOT_TOKEN", "")).strip()
        self.app_token = (app_token or os.getenv(f"{p_prefix}APP_TOKEN") or os.getenv("SLACK_APP_TOKEN", "")).strip()
        
        self.thread_personas: Dict[str, str] = {}
        self.thread_histories: Dict[str, List[Dict[str, str]]] = {}
        self.app: Optional[Any] = None
        self.handler: Optional[Any] = None

    def _validate_tokens(self) -> bool:
        if not self.bot_token or not self.app_token:
            return False
        if App is None or SocketModeHandler is None:
            print("⚠️ [Sympose Slack] slack-bolt / slack-sdk not installed. Run `pip install -r requirements.txt`.", file=sys.stderr)
            return False
        return True

    def _resolve_persona_and_prompt(self, text: str, thread_id: str) -> Tuple[str, str]:
        """Extracts target persona from explicit @handle mentions, aliases, or falls back to thread / default persona."""
        cleaned = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
        personas = self.pm.list_personas()
        
        # Build alias lookup map (e.g. mauri -> aurelius, marcus -> aurelius, sam -> samantha)
        alias_map: Dict[str, str] = {"mauri": "aurelius", "marcus": "aurelius", "sam": "samantha"}
        for p in personas:
            h = p["handle"].lower()
            alias_map[h] = h
            for part in p.get("name", "").lower().split():
                if len(part) >= 3:
                    alias_map[part] = h
            for al in p.get("aliases", []):
                alias_map[str(al).lower()] = h

        match = re.match(r"^@?([a-zA-Z0-9_\-]+)[:,\s]+(.*)$", cleaned, re.DOTALL)
        if match:
            candidate = match.group(1).lower()
            if candidate in alias_map:
                target = alias_map[candidate]
                self.thread_personas[thread_id] = target
                return target, match.group(2).strip()

        if cleaned.startswith("/switch"):
            parts = cleaned.split()
            if len(parts) > 1:
                target_key = parts[1].replace("@", "").lower()
                if target_key in alias_map:
                    target = alias_map[target_key]
                    self.thread_personas[thread_id] = target
                    return target, f"Switched active persona to @{target}."

        active_handle = self.thread_personas.get(thread_id, self.default_persona)
        if active_handle not in [p["handle"].lower() for p in personas]:
            active_handle = self.default_persona
        return active_handle, cleaned

    def _process_message(self, client: Any, event: Dict[str, Any], say: Any) -> None:
        """Processes incoming Slack message or app mention within an isolated thread context."""
        channel_id = event.get("channel", "")
        thread_ts = event.get("thread_ts") or event.get("ts", "")
        msg_ts = event.get("ts", "")
        raw_text = event.get("text", "")
        thread_id = f"{channel_id}:{thread_ts}"

        if not raw_text.strip() or event.get("bot_id") or event.get("subtype") == "bot_message":
            return

        handle, prompt = self._resolve_persona_and_prompt(raw_text, thread_id)
        profile = self.pm.get_profile(handle)
        name = profile.get("name", handle) if profile else handle
        print(f"📥 [Slack Event] @{handle} ({name}) handling message: {prompt[:60]}")

        try:
            client.reactions_add(channel=channel_id, timestamp=msg_ts, name="eyes")
        except Exception:
            pass

        th_key = f"{thread_id}:{handle}"
        self.engine.histories[handle] = self.thread_histories.get(th_key, [])

        chunks: List[str] = []
        try:
            for chunk in self.engine.chat_stream(handle, prompt):
                if chunk != "CLEARED_SESSION":
                    chunks.append(chunk)

            full_reply = "".join(chunks).strip()
            self.thread_histories[th_key] = self.engine.get_history(handle)

            slack_text = convert_md_to_slack_mrkdwn(full_reply)
            say(text=slack_text, thread_ts=thread_ts)

            try:
                client.reactions_remove(channel=channel_id, timestamp=msg_ts, name="eyes")
                client.reactions_add(channel=channel_id, timestamp=msg_ts, name="white_check_mark")
            except Exception:
                pass
        except Exception as e:
            logging.error(f"Error handling Slack event: {e}")
            say(text=f"⚠️ *{name} encountered an error:* `{e}`", thread_ts=thread_ts)

    def setup(self) -> bool:
        """Configures Bolt app event listeners and SocketMode handler."""
        if not self._validate_tokens():
            return False
        try:
            self.app = App(token=self.bot_token)

            @self.app.event("app_mention")
            def handle_app_mention(client, event, say):
                self._process_message(client, event, say)

            @self.app.event("message")
            def handle_direct_message(client, event, say):
                if event.get("channel_type") == "im" or event.get("thread_ts"):
                    self._process_message(client, event, say)

            self.handler = SocketModeHandler(self.app, self.app_token)
            return True
        except Exception as e:
            print(f"⚠️ [Sympose Slack] Failed to start @{self.default_persona}: {e}", file=sys.stderr)
            return False

    def start(self) -> None:
        """Launches the Slack Socket Mode daemon loop."""
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
            daemon = SlackDaemon(engine, default_persona=h)
            if daemon._validate_tokens() and not any(d.bot_token == daemon.bot_token for d in daemons):
                daemons.append(daemon)

        if not daemons:
            default_d = SlackDaemon(engine)
            if default_d.setup():
                daemons.append(default_d)
            else:
                print("⚠️ [Sympose Slack] Missing or invalid Slack tokens in .env.", file=sys.stderr)
                sys.exit(1)

        print(f"🚀 [Sympose] Launching {len(daemons)} Slack Agent(s)...")
        threads = []
        for d in daemons:
            if d.setup() and d.handler:
                print(f"  • @{d.default_persona} listening on Socket Mode...")
                t = threading.Thread(target=d.handler.start, daemon=True)
                t.start()
                threads.append(t)

        try:
            for t in threads:
                t.join()
        except (KeyboardInterrupt, SystemExit):
            print("\n🛑 [Sympose] All Slack Daemons terminated gracefully.")
