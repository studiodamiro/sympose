"""
Automated Memory Compactor, Distillation Engine & Shared Background-Hygiene
Infrastructure for Sympose. Consolidates working memory files, resolves
superseded facts, eliminates duplicate bloat, and hosts the bounded,
single-flight background-thread primitives shared by memory extraction,
session titling, and compaction itself.
"""

import logging
import os
import re
import threading
from collections.abc import Callable
from typing import Any

import litellm

log = logging.getLogger(__name__)

from sympose.config import DEFAULT_SUB_AGENT_MODEL, config_manager
from sympose.models import resolve_api_key

_FILE_LOCKS: dict[str, threading.Lock] = {}
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
_HYGIENE_SEMAPHORE = threading.Semaphore(
    max(1, int(config_manager.get("performance.hygiene_workers", 2)))
)

# In-flight compaction targets, guarded by _GLOBAL_LOCK — single-flight per file
# so a burst of turns crossing the compaction threshold before the first pass
# completes queues at most one compaction run per file, not one per turn.
_INFLIGHT_COMPACTIONS: set[str] = set()


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

    # A bullet phrased as a question or hedge was never confirmed as fact - it
    # must never be silently resolved into a flat assertion by compaction, no
    # matter what the distillation LLM decides. Telling the LLM this via the
    # compaction prompt alone was tried first and did not reliably hold once
    # the file got large and complex (confirmed live: a denied premise still
    # got asserted as settled fact) - this is the deterministic backstop.
    _UNRESOLVED_RE = re.compile(
        r"\?|\b(?:remember when|remember,? that we|didn'?t we|weren'?t we|"
        r"haven'?t we|wasn'?t it|did we (?:agree|decide)|are we (?:still )?"
        r"(?:planning|going) to)\b",
        re.IGNORECASE,
    )

    @classmethod
    def _looks_unresolved(cls, line: str) -> bool:
        return bool(cls._UNRESOLVED_RE.search(line))

    @classmethod
    def count_bullet_lines(cls, filepath: str) -> int:
        """Counts actionable bullet lines in a markdown memory file."""
        if not filepath or not os.path.exists(filepath):
            return 0
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return sum(
                1
                for line in lines
                if line.strip().startswith(("- ", "* "))
                and not line.strip().startswith(("- ---", "* ---"))
            )
        except Exception:
            return 0

    @classmethod
    def compact_file(
        cls,
        filepath: str,
        is_shared: bool = False,
        model: str | None = None,
        protect: list[str] | None = None,
    ) -> bool:
        """Executes an LLM distillation pass to clean and deduplicate a memory file."""
        if not filepath or not os.path.exists(filepath):
            return False

        lock = get_file_lock(filepath)
        try:
            with lock, open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                initial_lines = [
                    line.strip() for line in content.split("\n") if line.strip()
                ]
        except Exception:
            return False

        if not content:
            return False

        # Auto-protect any bullet that already reads as an unresolved question
        # or hedge, regardless of whether it's what triggered this particular
        # pass - every compaction re-checks every line, so this holds even if
        # an earlier pass somehow missed it. These are withheld from the LLM
        # entirely (not just protected in the output) - a model that sees an
        # unresolved claim can still draw its own confident conclusion from
        # it even when told not to (confirmed live), so the only reliable
        # fix is to never show it the claim in the first place.
        protect = list(protect or []) + [
            line
            for line in initial_lines
            if line.startswith(("- ", "* ")) and cls._looks_unresolved(line)
        ]
        protect_set = set(protect)
        content_for_llm = "\n".join(
            line for line in initial_lines if line not in protect_set
        )
        if not content_for_llm.strip():
            return False

        target_model = model or config_manager.get(
            "session.exit_behavior.summarization_model", DEFAULT_SUB_AGENT_MODEL
        )

        title = (
            "Shared Team Working Memory"
            if is_shared
            else os.path.splitext(os.path.basename(filepath))[0]
            .replace("_memory", "")
            .title()
            + " Working Memory"
        )

        prompt = (
            f"You are the Surgical Memory Compactor for Sympose AI.\n"
            f"Consolidate the following {title} into a high-density, clean markdown document.\n\n"
            "### STRICT COMPACTION DIRECTIVES:\n"
            "1. RESOLVE CONFLICTS & DRIFT: When facts conflict (e.g. updated codes, changed stack choices, new dates), preserve strictly the latest ground truth.\n"
            "2. ELIMINATE REDUNDANCY: Merge duplicate points (e.g. repeated user identity or duplicate architecture entries) into single crisp bullets.\n"
            "3. PRUNE TRANSIENT ARTIFACTS: Remove markdown separators (like '- ---'), temporary notes, and empty points.\n"
            "4. PRESERVE STRUCTURE: Start with `# {title}` and use clean bullet points (`- `).\n"
            "5. ZERO FABRICATION: Retain all unique, durable facts. Do not invent any new details.\n"
            "6. DO NOT RESOLVE AMBIGUITY INTO FACT: An entry phrased as a question, a hedge, "
            "or an unconfirmed premise (e.g. \"did we decide to...\", \"weren't we going to...\") "
            "is not a settled fact even if no contradicting entry exists. Preserve it verbatim, "
            "phrased with its original uncertainty, or drop it — never restate it as confirmed.\n\n"
            f"### ORIGINAL MEMORY:\n{content_for_llm}"
        )

        try:
            kwargs: dict[str, Any] = {
                "model": target_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "timeout": float(
                    config_manager.get("performance.request_timeout", 30.0)
                ),
            }
            api_key = resolve_api_key(target_model)
            if api_key:
                kwargs["api_key"] = api_key

            resp = litellm.completion(**kwargs)
            distilled = (resp.choices[0].message.content or "").strip()

            if (
                distilled
                and ("#" in distilled or "- " in distilled)
                and len(distilled) > 20
            ):
                with lock:
                    # Reconcile any lines appended while LLM was processing
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            current_content = f.read().strip()
                            current_lines = [
                                line.strip()
                                for line in current_content.split("\n")
                                if line.strip()
                            ]
                    except Exception:
                        current_lines = []

                    appended_lines = [
                        line for line in current_lines if line not in initial_lines
                    ]
                    # The fact whose own write crossed the compaction threshold
                    # survives regardless of the LLM's durability judgment — it
                    # was already in `initial_lines` (written before this pass
                    # started reading), so the appended-lines diff above never
                    # catches it on its own.
                    protected_missing = [
                        p
                        for p in (protect or [])
                        if p not in distilled and p not in appended_lines
                    ]
                    final_text = distilled.rstrip() + "\n"
                    extra_lines = appended_lines + protected_missing
                    if extra_lines:
                        final_text += "\n" + "\n".join(extra_lines) + "\n"

                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(final_text)
                return True
        except Exception as e:
            log.error("Memory compaction failed for %s: %s", filepath, e, exc_info=True)

        return False

    @classmethod
    def check_and_compact_async(
        cls,
        filepath: str,
        is_shared: bool = False,
        threshold: int | None = None,
        protect: list[str] | None = None,
    ) -> None:
        """Checks if line count exceeds threshold and runs compaction on the shared
        hygiene pool — single-flight per file, so repeated turns crossing the
        threshold before the first pass completes don't each queue their own run.
        `protect` is the fact whose own write just crossed the threshold — it must
        survive this pass regardless of the compactor's own durability judgment."""
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
                cls.compact_file(filepath, is_shared, protect=protect)
            finally:
                with _GLOBAL_LOCK:
                    _INFLIGHT_COMPACTIONS.discard(abs_path)

        run_hygiene_task(_run)
