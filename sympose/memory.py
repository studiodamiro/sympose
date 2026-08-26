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


def _load_prompt_tmpl(name: str, fallback: str) -> str:
    p = os.path.join("prompts", name)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f: return f.read().strip()
        except Exception: pass
    return fallback


class HeuristicGatedExtractor:
    """Evaluates turns for durable facts and triggers background extraction without blocking."""

    TRIGGER_PATTERNS = [
        r"\b(?:my\s+name\s+is|i\s+am|i'm|call\s+me)\b",
        r"\b(?:i\s+live\s+in|my\s+timezone\s+is|i\s+work\s+at|my\s+job\s+is|i\s+am\s+a)\b",
        r"\b(?:i\s+prefer|i\s+like|i\s+dislike|i\s+hate|always\s+use|never\s+use|my\s+favorite)\b",
        r"\b(?:remember\s+that|keep\s+in\s+mind|don't\s+forget|note\s+that|save\s+this)\b",
        r"\b(?:we\s+decided|the\s+architecture\s+is|we\s+are\s+building|the\s+stack\s+is)\b",
        r"\b(?:my\s+goal\s+is|the\s+deadline\s+is|we\s+need\s+to\s+ship)\b",
    ]

    SKIP_PATTERNS = [
        r"^(?:hi|hello|hey|yo|thanks|thank\s+you|ok|okay|cool|nice|yes|no|yep|nope)[\.\!\?]?$",
        r"^(?:clear|reset|delete|help|exit|quit|status|\/switch|\/save|\/clear|\/reset)",
        r"^\[SPAWN_WORKER:",
    ]

    @classmethod
    def should_extract(cls, user_message: str) -> bool:
        clean = user_message.strip().lower()
        if len(clean) < 8: return False
        for skip in cls.SKIP_PATTERNS:
            if re.search(skip, clean): return False
        for pat in cls.TRIGGER_PATTERNS:
            if re.search(pat, clean): return True
        return False

    @classmethod
    def extract_async(cls, handle: str, user_message: str, assistant_reply: str, pm: ProfileManager, config: Any) -> None:
        """Runs the extraction pass in a detached background daemon thread."""
        def _worker():
            try:
                model = config.get("session.exit_behavior.summarization_model", "gemini/gemini-3.5-flash-lite")
                tmpl = _load_prompt_tmpl("memory_extraction.md", "You are the silent memory archivist for Sympose AI.\nUser message: {{user_message}}\nAssistant reply: {{assistant_reply}}\n\nEvaluate if the user shared a DURABLE fact.\nIf NO: Output 'NONE'.\nIf YES: Output 1 bullet point '- '.")
                prompt = tmpl.replace("{{user_message}}", user_message).replace("{{assistant_reply}}", assistant_reply)
                kwargs = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "timeout": 5.0}
                for pfx, key in (("gemini/", "GEMINI_API_KEY"), ("anthropic/", "ANTHROPIC_API_KEY"), ("openai/", "OPENAI_API_KEY"), ("openrouter/", "OPENROUTER_API_KEY")):
                    if model.startswith(pfx) and os.getenv(key): kwargs["api_key"] = os.getenv(key)

                resp = litellm.completion(**kwargs)
                out = (resp.choices[0].message.content or "").strip()
                if out and out.upper() != "NONE" and out.startswith("-"): pm.append_memory(handle, out)
            except Exception: pass

        threading.Thread(target=_worker, daemon=True).start()


class SessionArchivist:
    """Handles LLM-driven session summarization, memory extraction, and note persistence."""

    def __init__(self, profile_manager: ProfileManager):
        self.pm, self.config = profile_manager, config_manager

    def trigger_background_extraction(self, handle: str, user_message: str, assistant_reply: str) -> None:
        if HeuristicGatedExtractor.should_extract(user_message):
            HeuristicGatedExtractor.extract_async(handle, user_message, assistant_reply, self.pm, self.config)

    def summarize_session(self, handle: str, history: List[Dict[str, str]], target: str = "both") -> Dict[str, Any]:
        profile = self.pm.get_profile(handle)
        if not profile: return {"status": "error", "message": f"Persona @{handle} not found."}
        if not history: return {"status": "empty", "message": "No active conversation turns to summarize."}

        transcript = "\n\n".join(f"{msg.get('role', 'unknown').capitalize()}: {msg.get('content', '')}" for msg in history)
        summarization_model = self.config.get("session.exit_behavior.summarization_model", "gemini/gemini-3.5-flash-lite")
        tmpl = _load_prompt_tmpl("session_summary.md", "You are the session archivist for Sympose Agent Hub.\nAnalyze session with @{{handle}} ({{name}}):\n\n### SECTION 1: PERSISTENT MEMORY BULLETS\n- Facts\n\n### SECTION 2: OBSIDIAN SESSION LOG\n## Overview\n\nCONVERSATION TRANSCRIPT:\n{{transcript}}")
        prompt = tmpl.replace("{{handle}}", handle).replace("{{name}}", str(profile.get("name", handle))).replace("{{transcript}}", transcript)

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
            elif summarization_model.startswith("openrouter/") and os.getenv("OPENROUTER_API_KEY"):
                kwargs["api_key"] = os.getenv("OPENROUTER_API_KEY")

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
