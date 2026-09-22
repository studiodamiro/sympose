"""`python -m sympose.cli` entry point."""

import os

from dotenv import load_dotenv

# Unlike `sympose/main.py` (the FastAPI server entrypoint), nothing else in
# this package loaded `.env` — harmless while the CLI was pure mock data,
# but now that chat grounding depends on `VAULT_PATHS` (docs/decisions/006),
# a bare `python -m sympose.cli` needs this too.
load_dotenv()

from sympose.cli.app import SymposeCLI  # noqa: E402 — after load_dotenv()

if __name__ == "__main__":
    SymposeCLI().run()
    # A model call can't be cancelled once its thread is blocked inside
    # litellm's network call (docs/decisions/007); quitting while one is
    # still in flight would otherwise hang here for up to
    # `model._REQUEST_TIMEOUT_SECONDS` — Python's normal interpreter
    # shutdown waits for every `concurrent.futures` worker thread still
    # running anywhere in the process, not just this app's own. `os._exit`
    # skips that wait entirely; Textual's own UI teardown has already
    # completed by the time `run()` returns, and nothing else here holds
    # state that needs Python's normal atexit/cleanup machinery.
    os._exit(0)
