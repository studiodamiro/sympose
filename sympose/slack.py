"""
🏛️ Sympose: Slack Socket Mode Daemon
Multi-persona concurrent router, thread context fetcher & event dispatcher.
"""

import atexit
import logging
import os
import re
import sys
import threading
import time
from collections import defaultdict
from typing import Any

try:
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
except ImportError:
    App, SocketModeHandler = None, None

from sympose import slack_heartbeat
from sympose.actions import ActionProcessor
from sympose.config import convert_md_to_slack_mrkdwn
from sympose.engine import PersonaEngine

log = logging.getLogger(__name__)


class SlackDaemon:
    """Slack Socket Mode integration with thread-isolated sessions and human-readable context."""

    def __init__(
        self,
        engine: PersonaEngine,
        default_persona: str | None = None,
        bot_token: str | None = None,
        app_token: str | None = None,
    ):
        self.engine, self.pm, self.config = engine, engine.pm, engine.config
        self.default_persona = (
            default_persona or self.config.get("runtime.default_persona").lower()
        )
        p = f"SLACK_{self.default_persona.upper()}_"
        self.bot_token = (
            bot_token
            or os.getenv(f"{p}BOT_TOKEN")
            or (
                os.getenv("SLACK_AURELIUS_BOT_TOKEN")
                if self.default_persona == "archia"
                else None
            )
            or os.getenv("SLACK_BOT_TOKEN", "")
        ).strip()
        self.app_token = (
            app_token
            or os.getenv(f"{p}APP_TOKEN")
            or (
                os.getenv("SLACK_AURELIUS_APP_TOKEN")
                if self.default_persona == "archia"
                else None
            )
            or os.getenv("SLACK_APP_TOKEN", "")
        ).strip()
        (
            self.thread_personas,
            self.thread_histories,
            self.app,
            self.handler,
            self.bot_user_id,
            self.bot_id,
            self.boot_ts,
        ) = {}, {}, None, None, "", "", time.time()
        # Per-instance — one SlackDaemon per persona (see the loop that spawns
        # them), so these must never be shared class-level state: two personas
        # sharing a cache could see one's bot silently filtered as the other's.
        self.user_cache: dict[str, str] = {}
        self.name_to_id: dict[str, str] = {}
        self.bot_user_ids: set[str] = set()
        self._is_setup = False
        # Per-channel semaphore — caps concurrent in-flight message processing
        self._channel_semaphores: dict[str, threading.Semaphore] = defaultdict(
            lambda: threading.Semaphore(
                int(self.config.get("performance.slack_max_concurrent"))
            )
        )
        u_card = self.pm._read_file_safe(
            os.path.join(
                getattr(self.pm, "profiles_dir", "profiles"), "user_profile.md"
            )
        )
        m = re.search(
            r"[-*]?\s*(?:\*\*|__)?(?:Primary\s+User|User|Name)(?:\*\*|__)?\s*:\s*([^\n\r]+)",
            u_card,
            re.IGNORECASE,
        )
        self.primary_user = (
            m.group(1).strip().strip("*_`")
            if m and m.group(1).strip()
            else (os.getenv("USER") or "User")
        )

    def _validate_tokens(self) -> bool:
        if (
            not self.bot_token
            or not self.app_token
            or App is None
            or SocketModeHandler is None
        ):
            if App is None:
                log.warning("[Sympose Slack] slack-bolt not installed.")
            return False
        return True

    def _resolve_user_name(self, client: Any, user_id: str) -> str:
        if not user_id or not user_id.startswith("U"):
            return user_id or "Participant"
        if user_id in self.user_cache:
            return self.user_cache[user_id]
        try:
            u_info = client.users_info(user=user_id).get("user", {})
            name = (
                u_info.get("profile", {}).get("display_name")
                or u_info.get("real_name")
                or u_info.get("name")
            )
            if name:
                self.user_cache[user_id] = name
                self.name_to_id[name.lower()] = user_id
                self.name_to_id[u_info.get("name", "").lower()] = user_id
                return name
        except Exception as e:
            log.debug(
                "[_resolve_user_name] users_info lookup failed for %s: %s", user_id, e
            )
        self.user_cache[user_id] = self.primary_user
        self.name_to_id[self.primary_user.lower()] = user_id
        return self.primary_user

    def _clean_mentions(self, client: Any, text: str) -> str:
        return re.sub(
            r"<@([A-Z0-9]+)>",
            lambda m: f"@{self._resolve_user_name(client, m.group(1))}",
            text,
        )

    def _format_outgoing_mentions(self, text: str) -> str:
        def replace_tag(m):
            tag = m.group(1).lower()
            if tag in self.name_to_id:
                return f"<@{self.name_to_id[tag]}>"
            if (
                tag in ("user", "human", "primary_user")
                and self.primary_user.lower() in self.name_to_id
            ):
                return f"<@{self.name_to_id[self.primary_user.lower()]}>"
            return m.group(0)

        return re.sub(r"@([a-zA-Z0-9_\-]+)", replace_tag, text)

    def _resolve_persona_and_prompt(self, text: str, thread_id: str) -> tuple[str, str]:
        cleaned, personas = (
            re.sub(r"<@[A-Z0-9]+>", "", text).strip(),
            self.pm.list_personas(),
        )
        alias_map = {p["handle"].lower(): p["handle"].lower() for p in personas}
        for p in personas:
            h = p["handle"].lower()
            for part in p.get("name", "").lower().split():
                if len(part) >= 3:
                    alias_map[part] = h
            for al in p.get("aliases", []):
                alias_map[str(al).lower()] = h

        gm = re.match(
            r"^(?:hi|hey|hello|good\s+morning|morning|good\s+afternoon|good\s+evening)\s+@?([a-zA-Z0-9_\-]+)[,:\s]*(.*)$",
            cleaned,
            re.IGNORECASE | re.DOTALL,
        )
        if gm and gm.group(1).lower() in alias_map:
            t = alias_map[gm.group(1).lower()]
            self.thread_personas[thread_id] = t
            return t, (gm.group(2).strip() or cleaned)

        m = re.match(r"^@?([a-zA-Z0-9_\-]+)[:,\s]+(.*)$", cleaned, re.DOTALL)
        if m and m.group(1).lower() in alias_map:
            t = alias_map[m.group(1).lower()]
            self.thread_personas[thread_id] = t
            return t, m.group(2).strip()

        if (
            cleaned.startswith("/switch")
            and len(parts := cleaned.split()) > 1
            and parts[1].replace("@", "").lower() in alias_map
        ):
            t = alias_map[parts[1].replace("@", "").lower()]
            self.thread_personas[thread_id] = t
            return t, f"Switched active persona to @{t}."

        active = self.thread_personas.get(thread_id, self.default_persona)
        return (
            active
            if active in [p["handle"].lower() for p in personas]
            else self.default_persona
        ), cleaned

    def _fetch_slack_context(
        self,
        client: Any,
        channel_id: str,
        thread_ts: str | None,
        current_ts: str,
        prompt: str,
    ) -> str:
        """Retrieves Slack thread replies or recent channel history with human-readable usernames."""
        if thread_ts:
            try:
                res = client.conversations_replies(
                    channel=channel_id,
                    ts=thread_ts,
                    limit=int(
                        self.config.get("performance.slack_thread_context_limit")
                    ),
                )
                if tl := [
                    f"- {self._resolve_user_name(client, m.get('user') or m.get('username') or '')}: {self._clean_mentions(client, m.get('text', '').strip())}"
                    for m in res.get("messages", [])
                    if m.get("ts") != current_ts and m.get("text", "").strip()
                ]:
                    return (
                        "### Slack Thread Context (Preceding Messages in this Thread):\n"
                        + "\n".join(tl)
                    )
            except Exception as e:
                logging.debug(f"Thread context: {e}")

        if re.search(
            r"\b(summarize|summary|catch\s*up|recap|what\s+happened|this\s+(?:thread|channel|conversation))\b",
            prompt,
            re.IGNORECASE,
        ):
            try:
                cl = [
                    f"- {self._resolve_user_name(client, m.get('user') or m.get('username') or '')}: {self._clean_mentions(client, m.get('text', '').strip())}"
                    for m in reversed(
                        client.conversations_history(channel=channel_id, limit=25).get(
                            "messages", []
                        )
                    )
                    if m.get("ts") != current_ts and m.get("text", "").strip()
                ]
                if cl:
                    return "### Recent Slack Channel History:\n" + "\n".join(cl)
            except Exception as e:
                logging.debug(f"Channel context: {e}")
        return ""

    @staticmethod
    def _conversation_key(channel_id: str, is_dm: bool, event: dict[str, Any]) -> str:
        """Identifies which ongoing conversation an event belongs to — the
        continuity boundary for memory, active-persona-per-thread tracking,
        and session archival.

        A DM is inherently one conversation (just the user and the persona),
        so it's keyed on the channel alone — stable across every message,
        Slack-threaded or not. Ordinary DM chat is never Slack-threaded (a
        user doesn't click "reply in thread" on themselves), so keying on
        `thread_ts` here — as this used to — meant every plain follow-up got
        its own fresh key (falling back to that message's own timestamp) and
        the persona lost all memory of the message before it.

        A channel can genuinely hold several separate conversations at once,
        so it stays keyed on Slack's own thread_ts, falling back to the
        triggering message's own ts for an unthreaded first message, and to
        the channel id as a last resort.
        """
        if is_dm:
            return channel_id
        return f"{channel_id}:{event.get('thread_ts') or event.get('ts') or channel_id}"

    def _should_skip_message(
        self, raw_text: str, msg_ts: str, sender: str, sender_bot: str
    ) -> bool:
        """True for an empty/stale message, or one that's this bot's own
        echo of its own reply."""
        if not raw_text.strip() or float(msg_ts or 0) < (
            getattr(self, "boot_ts", 0) - 5.0
        ):
            return True
        return bool(
            (getattr(self, "bot_user_id", "") and sender == self.bot_user_id)
            or (getattr(self, "bot_id", "") and sender_bot == self.bot_id)
        )

    def _maybe_append_bot_streak_notice(
        self,
        client: Any,
        channel_id: str,
        event: dict[str, Any],
        sender: str,
        sender_bot: str,
        prompt: str,
    ) -> str:
        """Appends a turn-limit notice to `prompt` when this message is
        itself from another bot and the thread has hit
        `performance.max_consecutive_bot_turns` consecutive bot replies —
        keeps two bots from talking forever."""
        is_bot_message = bool(
            sender_bot
            or sender in self.bot_user_ids
            or event.get("subtype") == "bot_message"
        )
        if not (is_bot_message and event.get("thread_ts")):
            return prompt
        try:
            msgs = client.conversations_replies(
                channel=channel_id, ts=event.get("thread_ts"), limit=8
            ).get("messages", [])
            streak = sum(
                1
                for m in reversed(msgs)
                if (
                    m.get("bot_id")
                    or m.get("user") in self.bot_user_ids
                    or m.get("subtype") == "bot_message"
                )
            )
            if streak >= int(self.config.get("performance.max_consecutive_bot_turns")):
                prompt += "\n\n[SYSTEM: Discussion turn limit reached. Deliver concluding summary for the user without tagging other bots.]"
        except Exception as e:
            log.debug(
                "[_process_message] bot-streak lookup failed for %s: %s",
                channel_id,
                e,
            )
        return prompt

    def _delete_thread_messages(
        self, client: Any, channel_id: str, thread_ts_val: str, thread_id: str
    ) -> None:
        try:
            for m in client.conversations_replies(
                channel=channel_id, ts=thread_ts_val, limit=100
            ).get("messages", []):
                try:
                    client.chat_delete(channel=channel_id, ts=m.get("ts"))
                except Exception as e:
                    log.debug(
                        "[thread wipe] chat_delete failed for ts=%s: %s",
                        m.get("ts"),
                        e,
                    )
        except Exception as e:
            log.debug(
                "[thread wipe] conversations_replies failed for %s: %s",
                thread_id,
                e,
            )

    def _handle_thread_wipe_request(
        self,
        client: Any,
        event: dict[str, Any],
        channel_id: str,
        msg_ts: str,
        thread_ts: str,
        thread_id: str,
        handle: str,
        prompt: str,
        say: Any,
    ) -> bool:
        """If `prompt` is a wipe request ("delete our thread", "/clear", …),
        clears local + Slack-side history for this thread. Returns True so
        the caller stops processing this message as a normal chat turn."""
        is_wipe = bool(
            re.search(
                r"\b(?:delete|clear|wipe|erase|purge|reset)\s+(?:our\s+|the\s+|this\s+)?(?:thread|chat|conversation|history|session|context|messages?)",
                prompt,
                re.IGNORECASE,
            )
        ) or prompt.strip() in ("/clear", "/delete", "/wipe", "/reset")
        if not is_wipe:
            return False

        th_key = f"{thread_id}:{handle}"
        self.thread_histories.pop(th_key, None)
        self.engine.reset_history(handle, session_id=th_key)
        if event.get("thread_ts"):
            self._delete_thread_messages(
                client, channel_id, event.get("thread_ts"), thread_id
            )
        try:
            client.reactions_remove(channel=channel_id, timestamp=msg_ts, name="eyes")
            client.reactions_add(channel=channel_id, timestamp=msg_ts, name="broom")
        except Exception as e:
            log.debug("[thread wipe] reaction swap (eyes->broom) failed: %s", e)
        if not re.search(
            r"\b(?:do\s*not\s*reply|no\s*reply|do\s*not\s*acknowledge|no\s*response|silent|silence)\b",
            prompt,
            re.IGNORECASE,
        ):
            say(
                text=f"🧹 Conversation history deleted for @{handle}.",
                thread_ts=thread_ts,
            )
        return True

    def _react_after_reply(
        self, client: Any, channel_id: str, msg_ts: str, raw_text: str, is_silent: bool
    ) -> None:
        try:
            client.reactions_remove(channel=channel_id, timestamp=msg_ts, name="eyes")
        except Exception as e:
            log.debug("[_process_message] reactions_remove(eyes) failed: %s", e)
        emojis = [
            m.group(1).strip().strip(":")
            for m in re.finditer(
                r"\[(?:ACTION:)?REACT:\s*([a-zA-Z0-9_\-+:]+?)\]",
                raw_text,
                re.IGNORECASE,
            )
        ] or (["white_check_mark"] if is_silent else [])
        for em in emojis:
            try:
                client.reactions_add(channel=channel_id, timestamp=msg_ts, name=em)
            except Exception as e:
                log.debug("[_process_message] reactions_add(%s) failed: %s", em, e)

    def _run_chat_turn_and_reply(
        self,
        client: Any,
        channel_id: str,
        msg_ts: str,
        thread_ts: str,
        th_key: str,
        handle: str,
        full_prompt: str,
        name: str,
        say: Any,
    ) -> None:
        try:
            chunks = [
                c
                for c in self.engine.chat_stream(handle, full_prompt, session_id=th_key)
                if c != "CLEARED_SESSION"
            ]
            self.thread_histories[th_key] = self.engine.get_history(
                handle, session_id=th_key
            )
            raw_text = "".join(chunks).strip()
            clean_text = ActionProcessor.strip_action_tags(raw_text)
            is_silent = not clean_text or clean_text.strip().lower() in (
                "(no response)",
                "no response",
                "(silence)",
                "...",
                "no response.",
            )
            if not is_silent:
                say(
                    text=self._format_outgoing_mentions(
                        convert_md_to_slack_mrkdwn(clean_text)
                    ),
                    thread_ts=thread_ts,
                )
            self._react_after_reply(client, channel_id, msg_ts, raw_text, is_silent)
        except Exception as e:
            log.error("[Slack Error] @%s: %s", handle, e, exc_info=True)
            say(text=f"⚠️ *{name} encountered an error:* `{e}`", thread_ts=thread_ts)

    def _process_message(self, client: Any, event: dict[str, Any], say: Any) -> None:
        channel_id, msg_ts, raw_text = (
            event.get("channel", ""),
            event.get("ts", ""),
            event.get("text", ""),
        )
        sender = event.get("user") or ""
        sender_bot = event.get("bot_id") or ""
        if self._should_skip_message(raw_text, msg_ts, sender, sender_bot):
            return

        is_dm = event.get("channel_type") == "im"
        thread_ts = (
            event.get("thread_ts")
            if is_dm
            else (event.get("thread_ts") or event.get("ts", ""))
        )
        thread_id = self._conversation_key(channel_id, is_dm, event)

        handle, prompt = self._resolve_persona_and_prompt(raw_text, thread_id)
        if (
            bool(os.getenv(f"SLACK_{handle.upper()}_BOT_TOKEN"))
            and handle != self.default_persona
        ):
            return

        prompt = self._maybe_append_bot_streak_notice(
            client, channel_id, event, sender, sender_bot, prompt
        )

        name = (
            self.pm.get_profile(handle).get("name", handle)
            if self.pm.get_profile(handle)
            else handle
        )
        slack_ctx = self._fetch_slack_context(
            client, channel_id, event.get("thread_ts"), msg_ts, prompt
        )
        full_prompt = f"{slack_ctx}\n\nUser Request: {prompt}" if slack_ctx else prompt

        log.info(
            "[Slack Event] @%s (%s) handling message: %s", handle, name, prompt[:60]
        )
        try:
            client.reactions_add(channel=channel_id, timestamp=msg_ts, name="eyes")
        except Exception as e:
            log.debug("[_process_message] reactions_add(eyes) failed: %s", e)

        th_key = f"{thread_id}:{handle}"
        if self._handle_thread_wipe_request(
            client, event, channel_id, msg_ts, thread_ts, thread_id, handle, prompt, say
        ):
            return

        self._run_chat_turn_and_reply(
            client, channel_id, msg_ts, thread_ts, th_key, handle, full_prompt, name, say
        )

    def setup(self) -> bool:
        if self._is_setup and self.handler:
            return True
        if not self._validate_tokens():
            return False
        try:
            self.app = App(token=self.bot_token)
            auth = self.app.client.auth_test()
            self.bot_user_id, self.bot_id = (
                auth.get("user_id", ""),
                auth.get("bot_id", ""),
            )
            self.bot_user_ids.add(self.bot_user_id)
            self.name_to_id[self.default_persona] = self.bot_user_id
            try:
                for u in self.app.client.users_list().get("members", []):
                    if u.get("is_bot") and u.get("id"):
                        self.bot_user_ids.add(u["id"])
                    for k in [
                        u.get("name"),
                        u.get("real_name"),
                        u.get("profile", {}).get("display_name"),
                    ]:
                        (
                            self.name_to_id.update({k.lower(): u["id"]})
                            if k and u.get("id")
                            else None
                        )
            except Exception as e:
                log.debug(
                    "[setup] users_list failed while priming bot/name cache: %s", e
                )
            self.app.event("app_mention")(
                lambda client, event, say: self._handle_event_async(client, event, say)
            )
            self.app.event("message")(
                lambda client, event, say: (
                    self._handle_event_async(client, event, say)
                    if (event.get("channel_type") == "im" or event.get("thread_ts"))
                    else None
                )
            )
            self.handler = SocketModeHandler(self.app, self.app_token)
            self._is_setup = True
            return True
        except Exception as e:
            log.error(
                "[Sympose Slack] Failed to start @%s: %s",
                self.default_persona,
                e,
                exc_info=True,
            )
            return False

    def _handle_event_async(self, client: Any, event: dict[str, Any], say: Any) -> None:
        """Dispatches _process_message in a daemon thread, rate-limited per channel."""
        channel_id = event.get("channel", "default")
        sem = self._channel_semaphores[channel_id]

        def _run():
            acquired = sem.acquire(blocking=False)
            if not acquired:
                # Channel is at capacity — add a clock reaction and queue
                try:
                    client.reactions_add(
                        channel=channel_id,
                        timestamp=event.get("ts", ""),
                        name="hourglass_flowing_sand",
                    )
                except Exception as e:
                    log.debug("Failed to add queued-message reaction: %s", e)
                sem.acquire(blocking=True)  # wait for a slot
                try:
                    client.reactions_remove(
                        channel=channel_id,
                        timestamp=event.get("ts", ""),
                        name="hourglass_flowing_sand",
                    )
                except Exception as e:
                    log.debug("Failed to remove queued-message reaction: %s", e)
            try:
                self._process_message(client, event, say)
            finally:
                sem.release()

        threading.Thread(target=_run, daemon=True).start()

    def start(self) -> None:
        while True:
            try:
                if self.setup() and self.handler:
                    label = (self.pm.get_profile(self.default_persona) or {}).get(
                        "name"
                    ) or self.default_persona
                    # handler.connect() + block, not handler.start(): the latter's
                    # slack_bolt banner ("⚡️ Bolt app is running!") is a bare print()
                    # with no persona context and cannot be silenced.
                    self.handler.connect()
                    print(
                        f"⚡ @{self.default_persona} ({label}) live on Socket Mode",
                        flush=True,
                    )
                    threading.Event().wait()
            except Exception as e:
                self._is_setup = False
                log.warning(
                    "[Slack Reconnect] @%s: %s. Retrying in 3s...",
                    self.default_persona,
                    e,
                )
                time.sleep(3)


class MultiPersonaSlackRunner:
    """Discovers and runs all configured persona Slack bots concurrently."""

    @classmethod
    def run_all(
        cls,
        engine: PersonaEngine,
        persona_override: str | None = None,
        workspace_dir: str | None = None,
    ) -> None:
        daemons = [
            d
            for h in (
                [persona_override.lower()]
                if persona_override
                else [p["handle"].lower() for p in engine.pm.list_personas()]
            )
            if (d := SlackDaemon(engine, default_persona=h))._validate_tokens()
            and d.setup()
        ]
        if not daemons:
            sys.exit("⚠️ [Sympose Slack] Missing or invalid Slack tokens in .env.")
        log.info("[Sympose] Launching %d Slack Persona(s)...", len(daemons))
        if workspace_dir:
            cls._start_heartbeat(workspace_dir, [d.default_persona for d in daemons])
        threads = [threading.Thread(target=d.start, daemon=True) for d in daemons]
        for t in threads:
            t.start()
        try:
            for t in threads:
                t.join()
        except (KeyboardInterrupt, SystemExit):
            pass

    @staticmethod
    def _start_heartbeat(workspace_dir: str, personas: list[str]) -> None:
        """Stamp `.slack_heartbeat.json` now and every `WRITE_INTERVAL`s from a
        daemon thread, so `GET /api/slack/status` can tell the dashboard whether
        Slack is live (ADR-082). Cleared on a clean exit."""
        slack_heartbeat.write_heartbeat(workspace_dir, personas)
        atexit.register(slack_heartbeat.clear_heartbeat, workspace_dir)

        def _loop() -> None:
            while True:
                time.sleep(slack_heartbeat.WRITE_INTERVAL)
                slack_heartbeat.write_heartbeat(workspace_dir, personas)

        threading.Thread(target=_loop, daemon=True, name="slack-heartbeat").start()
