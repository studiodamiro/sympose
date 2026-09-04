"""
Automated Memory Compactor, Distillation Engine & Shared Background-Hygiene
Infrastructure for Sympose. Consolidates working memory files, resolves
superseded facts, eliminates duplicate bloat, and hosts the bounded,
single-flight background-thread primitives shared by memory extraction,
session titling, and compaction itself.
"""

import os
import re
import logging
import threading
from typing import Optional, Dict, Any, Callable, Set
import litellm

log = logging.getLogger(__name__)

from sympose.config import config_manager, DEFAULT_WORKER_MODEL


_FILE_LOCKS: Dict[str, threading.Lock] = {}
_GLOBAL_LOCK = threading.Lock()


def get_file_lock(filepath: str) -> threading.Lock:
    """Returns a process-wide mutex for the given file path to avoid write conflicts."""
    abs_p = os.path.abspath(filepath)
    with _GLOBAL_LOCK:
        if abs_p not in _FILE_LOCKS:
            _FILE_LOCKS[abs_p] = threading.Lock()
        return _FILE_LOCKS[abs_p]


# ---------------------------------------------------------------------------
# Bounded background-hygiene task runner — shared by memory extraction,
# session titling, and memory compaction. A semaphore-gated daemon thread per
# task, NOT concurrent.futures.ThreadPoolExecutor: that pool's worker threads
# are non-daemon by design (its atexit hook joins them), which would make CLI
# `quit` block on any in-flight background LLM call. This keeps process exit
# instant while still capping concurrent background calls under load.
# ---------------------------------------------------------------------------
_HYGIENE_SEMAPHORE = threading.Semaphore(max(1, int(config_manager.get("performance.hygiene_workers", 2))))

# In-flight compaction targets, guarded by _GLOBAL_LOCK — single-flight per file
# so a burst of turns crossing the compaction threshold before the first pass
# completes queues at most one compaction run per file, not one per turn.
_INFLIGHT_COMPACTIONS: Set[str] = set()


def run_hygiene_task(target: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Runs a best-effort background hygiene callable on the bounded hygiene pool."""
    def _run() -> None:
        with _HYGIENE_SEMAPHORE:
            try:
                target(*args, **kwargs)
            except Exception:
                log.debug("[hygiene] background task failed", exc_info=True)

    threading.Thread(target=_run, daemon=True).start()


class MemoryCompactor:
    """Consolidates and prunes markdown working memory files when line counts exceed thresholds."""

    @classmethod
    def count_bullet_lines(cls, filepath: str) -> int:
        """Counts actionable bullet lines in a markdown memory file."""
        if not filepath or not os.path.exists(filepath):
            return 0
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return sum(1 for l in lines if l.strip().startswith(("- ", "* ")) and not l.strip().startswith(("- ---", "* ---")))
        except Exception:
            return 0

    @classmethod
    def compact_file(cls, filepath: str, is_shared: bool = False, model: Optional[str] = None) -> bool:
        """Executes an LLM distillation pass to clean and deduplicate a memory file."""
        if not filepath or not os.path.exists(filepath):
            return False

        lock = get_file_lock(filepath)
        try:
            with lock:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    initial_lines = [l.strip() for l in content.split("\n") if l.strip()]
        except Exception:
            return False

        if not content:
            return False

        target_model = model or config_manager.get(
            "session.exit_behavior.summarization_model",
            DEFAULT_WORKER_MODEL
        )

        title = "Shared Team Working Memory" if is_shared else os.path.splitext(os.path.basename(filepath))[0].replace("_memory", "").title() + " Working Memory"

        prompt = (
            f"You are the Surgical Memory Compactor for Sympose AI.\n"
            f"Consolidate the following {title} into a high-density, clean markdown document.\n\n"
            "### STRICT COMPACTION DIRECTIVES:\n"
            "1. RESOLVE CONFLICTS & DRIFT: When facts conflict (e.g. updated codes, changed stack choices, new dates), preserve strictly the latest ground truth.\n"
            "2. ELIMINATE REDUNDANCY: Merge duplicate points (e.g. repeated user identity or duplicate architecture entries) into single crisp bullets.\n"
            "3. PRUNE TRANSIENT ARTIFACTS: Remove markdown separators (like '- ---'), temporary notes, and empty points.\n"
            "4. PRESERVE STRUCTURE: Start with `# {title}` and use clean bullet points (`- `).\n"
            "5. ZERO FABRICATION: Retain all unique, durable facts. Do not invent any new details.\n\n"
            f"### ORIGINAL MEMORY:\n{content}"
        )

        try:
            kwargs: Dict[str, Any] = {
                "model": target_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "timeout": float(config_manager.get("performance.request_timeout", 30.0)),
            }
            if target_model.startswith("gemini/") and os.getenv("GEMINI_API_KEY"):
                kwargs["api_key"] = os.getenv("GEMINI_API_KEY")
            elif target_model.startswith("anthropic/") and os.getenv("ANTHROPIC_API_KEY"):
                kwargs["api_key"] = os.getenv("ANTHROPIC_API_KEY")
            elif target_model.startswith("openai/") and os.getenv("OPENAI_API_KEY"):
                kwargs["api_key"] = os.getenv("OPENAI_API_KEY")
            elif target_model.startswith("openrouter/") and os.getenv("OPENROUTER_API_KEY"):
                kwargs["api_key"] = os.getenv("OPENROUTER_API_KEY")

            resp = litellm.completion(**kwargs)
            distilled = (resp.choices[0].message.content or "").strip()

            if distilled and ("#" in distilled or "- " in distilled) and len(distilled) > 20:
                with lock:
                    # Reconcile any lines appended while LLM was processing
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            current_content = f.read().strip()
                            current_lines = [l.strip() for l in current_content.split("\n") if l.strip()]
                    except Exception:
                        current_lines = []

                    appended_lines = [l for l in current_lines if l not in initial_lines]
                    final_text = distilled.rstrip() + "\n"
                    if appended_lines:
                        final_text += "\n" + "\n".join(appended_lines) + "\n"

                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(final_text)
                return True
        except Exception as e:
            log.error("Memory compaction failed for %s: %s", filepath, e, exc_info=True)

        return False

    @classmethod
    def check_and_compact_async(cls, filepath: str, is_shared: bool = False, threshold: Optional[int] = None) -> None:
        """Checks if line count exceeds threshold and runs compaction on the shared
        hygiene pool — single-flight per file, so repeated turns crossing the
        threshold before the first pass completes don't each queue their own run."""
        auto_enabled = bool(config_manager.get("memory.auto_compact", True))
        if not auto_enabled:
            return

        limit = threshold or int(config_manager.get("memory.compaction_threshold", 25))
        if cls.count_bullet_lines(filepath) < limit:
            return

        abs_path = os.path.abspath(filepath)
        with _GLOBAL_LOCK:
            if abs_path in _INFLIGHT_COMPACTIONS:
                return
            _INFLIGHT_COMPACTIONS.add(abs_path)

        def _run() -> None:
            try:
                cls.compact_file(filepath, is_shared)
            finally:
                with _GLOBAL_LOCK:
                    _INFLIGHT_COMPACTIONS.discard(abs_path)

        run_hygiene_task(_run)
