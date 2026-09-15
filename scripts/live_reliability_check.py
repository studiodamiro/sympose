#!/usr/bin/env python3
"""
Live reliability check: runs the same message against a persona multiple
times per model, fresh session each time, and reports a hit rate.

A single live transcript is one data point, not a reliability number - a
local model samples at nonzero temperature, so a scenario that works once
can still fail on the next identical run. This exists to turn "I tried it
and it worked" into an actual pass rate across repeated, fresh runs,
against local and cloud models side by side.

This makes real LLM calls (local and/or cloud) - it is a manual live-testing
tool, not part of the pytest suite, and is not run in CI.

Usage:
    .venv/bin/python scripts/live_reliability_check.py \\
        --message "hey sam lets play our favorite game. lets do Movies. g!" \\
        --check roulette \\
        --models ollama/gemma4:e4b,gemini/gemini-3.6-flash \\
        --runs 6 \\
        --persona samantha
"""

import argparse
import sys

sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])

from sympose.profiles import ProfileManager  # noqa: E402
from sympose.engine import PersonaEngine  # noqa: E402


def run_once(engine: PersonaEngine, handle: str, message: str, model: str | None) -> str:
    session_id = engine.new_session(handle)
    if model:
        engine.set_model_override(handle, model)
    else:
        engine.clear_model_override(handle)
    return "".join(engine.chat_stream(handle, message, session_id=session_id))


def check_model(
    engine: PersonaEngine, handle: str, message: str, model: str | None,
    check: str, runs: int,
) -> tuple[int, int]:
    label = model or "(profile default)"
    hits = 0
    for i in range(runs):
        reply = run_once(engine, handle, message, model)
        ok = check.lower() in reply.lower()
        hits += ok
        flag = "OK  " if ok else "MISS"
        preview = reply[:160].replace("\n", " ")
        print(f"[{label} #{i + 1}] {flag} -> {preview}")
    print(f"\n{label}: {hits}/{runs} hit rate on \"{check}\"\n")
    return hits, runs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message", required=True, help="User message to send.")
    parser.add_argument(
        "--check", required=True,
        help="Case-insensitive substring the reply must contain to count as a hit.",
    )
    parser.add_argument(
        "--models", default="",
        help="Comma-separated model overrides to test, e.g. "
        "'ollama/gemma4:e4b,gemini/gemini-3.6-flash'. Empty entry = profile default.",
    )
    parser.add_argument("--runs", type=int, default=5, help="Runs per model.")
    parser.add_argument("--persona", default="samantha", help="Persona handle.")
    args = parser.parse_args()

    pm = ProfileManager()
    print(f"profiles_dir: {pm.profiles_dir}\n")
    engine = PersonaEngine(pm)

    models = [m.strip() or None for m in args.models.split(",")] if args.models else [None]
    results = [
        check_model(engine, args.persona, args.message, model, args.check, args.runs)
        for model in models
    ]

    print("=== SUMMARY ===")
    for model, (hits, runs) in zip(models, results):
        print(f"{model or '(profile default)'}: {hits}/{runs}")


if __name__ == "__main__":
    main()
