"""Dev entry point: `python -m sympose.main`. Reads `VAULT_PATHS` (and
optionally `SYMPOSE_PROFILES_DIR`) from the environment — see `.env.example`."""

import os

import uvicorn

from sympose.envfile import load_env

load_env()

from sympose.server import create_app  # noqa: E402 — after load_env()

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "sympose.main:app",
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
