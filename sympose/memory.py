"""
Session Archival, Distillation & Heuristic Gated Memory Management for Sympose.
"""

import logging
import re
from typing import Any, ClassVar

log = logging.getLogger(__name__)

import litellm

from sympose.compactor import run_hygiene_task
from sympose.config import DEFAULT_CHAT_MODEL, config_manager
from sympose.models import resolve_api_key
from sympose.profiles import ProfileManager
from sympose.prompt_assets import load_prompt
from sympose.vault import VaultManager


def _load_prompt_tmpl(name: str, fallback: str) -> str:
    return load_prompt(name, fallback)


class HeuristicGatedExtractor:
    """Evaluates turns for durable facts and triggers background extraction without blocking."""

    TRIGGER_PATTERNS: ClassVar[list[str]] = [
        r"\b(?:my\s+name\s+is|i\s+am|i'm|call\s+me)\b",
        r"\b(?:i\s+live\s+in|my\s+timezone\s+is|i\s+work\s+at|my\s+job\s+is|i\s+am\s+a)\b",
        r"\b(?:i\s+prefer|i\s+like|i\s+dislike|i\s+hate|always\s+use|never\s+use|my\s+favorite)\b",
        r"\b(?:remember\s+that|keep\s+in\s+mind|don't\s+forget|note\s+that|save\s+this)\b",
        r"\b(?:we\s+decided|the\s+architecture\s+is|we\s+are\s+building|the\s+stack\s+is)\b",
        r"\b(?:my\s+goal\s+is|the\s+deadline\s+is|we\s+need\s+to\s+ship)\b",
    ]

    SKIP_PATTERNS: ClassVar[list[str]] = [
        r"^(?:hi|hello|hey|yo|thanks|thank\s+you|ok|okay|cool|nice|yes|no|yep|nope)[\.\!\?]?$",
        r"^(?:clear|reset|delete|help|exit|quit|status|\/switch|\/save|\/clear|\/reset)",
        r"^\[SPAWN_SUB_AGENT:",
    ]

    @classmethod
    def should_extract(cls, user_message: str) -> bool:
        clean = user_message.strip().lower()
        if len(clean) < 8:
            return False
        for skip in cls.SKIP_PATTERNS:
            if re.search(skip, clean):
                return False
        for pat in cls.TRIGGER_PATTERNS:
            if re.search(pat, clean):
                return True
        return False

    @classmethod
    def extract_async(
        cls,
        handle: str,
        user_message: str,
        assistant_reply: str,
        pm: ProfileManager,
        config: Any,
    ) -> None:
        """Runs the extraction pass on the shared bounded background-hygiene pool."""

        def _worker():
            try:
                model = (
                    config.get("session.exit_behavior.summarization_model")
                    or DEFAULT_CHAT_MODEL
                )
                tmpl = _load_prompt_tmpl(
                    "memory_extraction.md",
                    "You are the silent memory archivist for Sympose AI.\nUser message: {{user_message}}\nAssistant reply: {{assistant_reply}}\n\nEvaluate if the user shared a DURABLE fact.\nIf NO: Output 'NONE'.\nIf YES: Output 1 bullet point '- '.",
                )
                prompt = tmpl.replace("{{user_message}}", user_message).replace(
                    "{{assistant_reply}}", assistant_reply
                )
                # Use a dedicated short timeout for background daemon threads to
                # prevent pileup under slow API conditions
                bg_timeout = float(config.get("memory.extraction_timeout"))
                kwargs = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "timeout": bg_timeout,
                }
                api_key = resolve_api_key(model)
                if api_key:
                    kwargs["api_key"] = api_key

                resp = litellm.completion(**kwargs)
                out = (resp.choices[0].message.content or "").strip()
                if out and out.upper() != "NONE":
                    bullets = [
                        line.strip()
                        for line in out.splitlines()
                        if line.strip().startswith(("- ", "* "))
                    ]
                    if bullets:
                        pm.append_memory(handle, "\n".join(bullets))
            except Exception as exc:
                log.debug(
                    "[memory.extract_async] suppressed error for @%s: %s", handle, exc
                )

        run_hygiene_task(_worker)


class SessionArchivist:
    """Handles LLM-driven session summarization, memory extraction, and note persistence."""

    def __init__(self, profile_manager: ProfileManager):
        self.pm, self.config = profile_manager, config_manager

    def trigger_background_extraction(
        self, handle: str, user_message: str, assistant_reply: str
    ) -> None:
        if HeuristicGatedExtractor.should_extract(user_message):
            HeuristicGatedExtractor.extract_async(
                handle, user_message, assistant_reply, self.pm, self.config
            )

    def summarize_session(
        self, handle: str, history: list[dict[str, str]], target: str = "both"
    ) -> dict[str, Any]:
        profile = self.pm.get_profile(handle)
        if not profile:
            return {"status": "error", "message": f"Persona @{handle} not found."}
        if not history:
            return {
                "status": "empty",
                "message": "No active conversation turns to summarize.",
            }

        transcript = "\n\n".join(
            f"{msg.get('role', 'unknown').capitalize()}: {msg.get('content', '')}"
            for msg in history
        )
        summarization_model = (
            self.config.get("session.exit_behavior.summarization_model")
            or DEFAULT_CHAT_MODEL
        )
        tmpl = _load_prompt_tmpl(
            "session_summary.md",
            "You are the session archivist for Sympose Persona Hub.\nAnalyze session with @{{handle}} ({{name}}):\n\n### SECTION 1: PERSISTENT MEMORY BULLETS\n- Facts\n\n### SECTION 2: OBSIDIAN SESSION LOG\n## Overview\n\nCONVERSATION TRANSCRIPT:\n{{transcript}}",
        )
        prompt = (
            tmpl.replace("{{handle}}", handle)
            .replace("{{name}}", str(profile.get("name", handle)))
            .replace("{{transcript}}", transcript)
        )

        try:
            kwargs: dict[str, Any] = {
                "model": summarization_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "timeout": float(self.config.get("performance.request_timeout")),
            }
            api_key = resolve_api_key(summarization_model)
            if api_key:
                kwargs["api_key"] = api_key

            resp = litellm.completion(**kwargs)
            raw_text = resp.choices[0].message.content or ""

            # Resilient section extraction
            sec1 = re.search(
                r"(?:###\s*SECTION\s*1[^\n]*|(?:\*\*|\#\#)?\s*SECTION\s*1[^\n]*)(.*?)(?:###\s*SECTION\s*2|(?:\*\*|\#\#)?\s*SECTION\s*2|$)",
                raw_text,
                re.IGNORECASE | re.DOTALL,
            )
            sec2 = re.search(
                r"(?:###\s*SECTION\s*2[^\n]*|(?:\*\*|\#\#)?\s*SECTION\s*2[^\n]*)(.*)$",
                raw_text,
                re.IGNORECASE | re.DOTALL,
            )

            memory_raw = (
                sec1.group(1).strip() if (sec1 and sec1.group(1).strip()) else ""
            )
            memory_bullets = [
                line.strip()
                for line in memory_raw.splitlines()
                if line.strip().startswith(("- ", "* "))
            ]
            memory_part = "\n".join(memory_bullets)
            obsidian_part = (
                sec2.group(1).strip()
                if (sec2 and sec2.group(1).strip())
                else raw_text.strip()
            )

            results: dict[str, Any] = {"status": "success", "targets_saved": []}

            if target in ("memory", "both") and memory_part:
                if self.pm.append_memory(handle, memory_part):
                    mem_file = profile.get(
                        "memory_file", f"profiles/{handle}_memory.md"
                    )
                    results["targets_saved"].append(f"Memory: `{mem_file}`")
                    results["memory_content"] = memory_part

            if target in ("obsidian", "both") and obsidian_part:
                subfolder = self.config.get("session.exit_behavior.obsidian_subfolder")
                save_msg = VaultManager.write_session_note(
                    profile, obsidian_part, subfolder=subfolder
                )
                results["targets_saved"].append(save_msg)
                results["obsidian_content"] = obsidian_part

            return results

        except Exception as e:
            return {"status": "error", "message": f"Summarization failed: {e}"}
