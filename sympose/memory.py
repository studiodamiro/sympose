"""
Session Archival, Distillation & Heuristic Gated Memory Management for Sympose.
"""

import os
import re
import threading
from typing import Dict, List, Any, Optional

from sympose.config import config_manager
import litellm

from sympose.profiles import ProfileManager
from sympose.vault import VaultManager


class HeuristicGatedExtractor:
    """Evaluates turns for durable facts and triggers background extraction without blocking."""

    TRIGGER_PATTERNS = [
        r"\b(i\s+will|i\s+plan|i\s+need|i\s+want|i\s+am\s+going\s+to|i\s+prefer)\b",
        r"\b(we\s+decided|we\s+are\s+using|we\s+switched|let\'?s\s+use|our\s+stack|our\s+database)\b",
        r"\b(on\s+(?:january|february|march|april|may|june|july|august|september|october|november|december))\b",
        r"\b(my\s+name\s+is|my\s+favorite|my\s+timezone|my\s+role|i\s+live\s+in)\b",
        r"\b(rule|constraint|never\s+use|always\s+use|deploy\s+to|secret|credential)\b",
    ]

    SKIP_PATTERNS = [
        r"^(hi|hello|hey|thanks|thank you|ok|okay|cool|great|bye|quit|exit|ping)\b",
        r"^(what is|who is|how do i|explain|summarize|convert)\b",
    ]

    @classmethod
    def should_extract(cls, user_message: str) -> bool:
        clean = user_message.strip().lower()
        if len(clean) < 12 or clean.startswith("/"):
            return False
        for skip in cls.SKIP_PATTERNS:
            if re.search(skip, clean):
                return False
        for pat in cls.TRIGGER_PATTERNS:
            if re.search(pat, clean):
                return True
        return False

    @classmethod
    def extract_async(cls, handle: str, user_message: str, assistant_reply: str, pm: ProfileManager, config: Any) -> None:
        """Runs the extraction pass in a detached background daemon thread."""
        def _worker():
            try:
                model = config.get("session.exit_behavior.summarization_model", "gemini/gemini-3.5-flash-lite")
                prompt = (
                    "You are the silent memory archivist for Sympose AI.\n"
                    f"User message: {user_message}\n"
                    f"Assistant reply: {assistant_reply}\n\n"
                    "Evaluate if the user shared a DURABLE, permanent fact, project decision, technical constraint, schedule, or personal preference that must be remembered in future sessions.\n"
                    "If NO: Output strictly 'NONE'.\n"
                    "If YES: Output exactly 1 concise bullet point starting with '- ' summarizing the enduring fact."
                )
                kwargs = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "timeout": 5.0,
                }
                if model.startswith("gemini/") and os.getenv("GEMINI_API_KEY"):
                    kwargs["api_key"] = os.getenv("GEMINI_API_KEY")
                elif model.startswith("anthropic/") and os.getenv("ANTHROPIC_API_KEY"):
                    kwargs["api_key"] = os.getenv("ANTHROPIC_API_KEY")
                elif model.startswith("openai/") and os.getenv("OPENAI_API_KEY"):
                    kwargs["api_key"] = os.getenv("OPENAI_API_KEY")

                resp = litellm.completion(**kwargs)
                out = (resp.choices[0].message.content or "").strip()
                if out and out.upper() != "NONE" and out.startswith("-"):
                    pm.append_memory(handle, out)
            except Exception:
                pass

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()


class SessionArchivist:
    """Handles LLM-driven session summarization, memory extraction, and note persistence."""

    def __init__(self, profile_manager: ProfileManager):
        self.pm = profile_manager
        self.config = config_manager

    def trigger_background_extraction(self, handle: str, user_message: str, assistant_reply: str) -> None:
        """Evaluates heuristic gate and triggers async shadow extraction."""
        if HeuristicGatedExtractor.should_extract(user_message):
            HeuristicGatedExtractor.extract_async(handle, user_message, assistant_reply, self.pm, self.config)

    def summarize_session(
        self,
        handle: str,
        history: List[Dict[str, str]],
        target: str = "both"
    ) -> Dict[str, Any]:
        """Synthesizes conversation history and saves to persistent memory and/or Obsidian."""
        profile = self.pm.get_profile(handle)
        if not profile:
            return {"status": "error", "message": f"Persona @{handle} not found."}

        if not history:
            return {"status": "empty", "message": "No active conversation turns to summarize."}

        transcript_lines = [
            f"{msg.get('role', 'unknown').capitalize()}: {msg.get('content', '')}"
            for msg in history
        ]
        transcript = "\n\n".join(transcript_lines)

        summarization_model = self.config.get(
            "session.exit_behavior.summarization_model",
            "gemini/gemini-3.5-flash-lite"
        )

        prompt = (
            f"You are the session archivist for Sympose Agent Hub. "
            f"Analyze the following conversation session with agent @{handle} ({profile.get('name')}) "
            f"and produce two structured sections separated exactly as shown below.\n\n"
            f"### SECTION 1: PERSISTENT MEMORY BULLETS\n"
            f"Provide 2-4 concise, high-signal bullet points of durable facts, technical decisions, or user preferences "
            f"that should be remembered in future sessions. Format every line starting with '- '.\n\n"
            f"### SECTION 2: OBSIDIAN SESSION LOG\n"
            f"Provide a structured Markdown session log covering:\n"
            f"## Overview & Intent\n"
            f"## Decisions & Code Highlights\n"
            f"## Action Items & Next Steps\n\n"
            f"CONVERSATION TRANSCRIPT:\n"
            f"{transcript}"
        )

        try:
            kwargs: Dict[str, Any] = {
                "model": summarization_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "timeout": float(self.config.get("performance.request_timeout", 10.0)),
            }
            if summarization_model.startswith("gemini/") and os.getenv("GEMINI_API_KEY"):
                kwargs["api_key"] = os.getenv("GEMINI_API_KEY")
            elif summarization_model.startswith("anthropic/") and os.getenv("ANTHROPIC_API_KEY"):
                kwargs["api_key"] = os.getenv("ANTHROPIC_API_KEY")
            elif summarization_model.startswith("openai/") and os.getenv("OPENAI_API_KEY"):
                kwargs["api_key"] = os.getenv("OPENAI_API_KEY")

            resp = litellm.completion(**kwargs)
            raw_text = resp.choices[0].message.content or ""

            # Resilient section extraction
            sec1 = re.search(
                r"(?:###\s*SECTION\s*1[^\n]*|(?:\*\*|\#\#)?\s*SECTION\s*1[^\n]*)(.*?)(?:###\s*SECTION\s*2|(?:\*\*|\#\#)?\s*SECTION\s*2|$)",
                raw_text,
                re.IGNORECASE | re.DOTALL
            )
            sec2 = re.search(
                r"(?:###\s*SECTION\s*2[^\n]*|(?:\*\*|\#\#)?\s*SECTION\s*2[^\n]*)(.*)$",
                raw_text,
                re.IGNORECASE | re.DOTALL
            )

            memory_part = sec1.group(1).strip() if (sec1 and sec1.group(1).strip()) else raw_text.strip()
            obsidian_part = sec2.group(1).strip() if (sec2 and sec2.group(1).strip()) else raw_text.strip()

            results: Dict[str, Any] = {"status": "success", "targets_saved": []}

            if target in ("memory", "both") and memory_part:
                if self.pm.append_memory(handle, memory_part):
                    mem_file = profile.get("memory_file", f"profiles/{handle}_memory.md")
                    results["targets_saved"].append(f"Memory: `{mem_file}`")
                    results["memory_content"] = memory_part

            if target in ("obsidian", "both") and obsidian_part:
                subfolder = self.config.get("session.exit_behavior.obsidian_subfolder", "Sessions")
                save_msg = VaultManager.write_session_note(profile, obsidian_part, subfolder=subfolder)
                results["targets_saved"].append(save_msg)
                results["obsidian_content"] = obsidian_part

            return results

        except Exception as e:
            return {"status": "error", "message": f"Summarization failed: {e}"}
