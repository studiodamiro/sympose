"""
Model Discovery, Provider-Key Resolution, and OpenRouter Catalog Manager
for Sympose. Provides fast local caching, catalog search, dynamic
tab-completion candidates, and the one place `target_model` -> API key
resolution lives — this used to be copy-pasted across five call sites
(engine.py, workers.py, compactor.py, memory.py x2, sessions.py), each a
verbatim or near-verbatim rewrite of the same four-provider prefix match.
"""

import json
import logging
import os
import time
import urllib.request
from typing import Any, ClassVar

log = logging.getLogger(__name__)

# (litellm provider prefix, env var to read the API key from). Order only
# matters in that a model string matches at most one of these — litellm
# provider prefixes never nest (an OpenRouter-routed Anthropic model is
# "openrouter/anthropic/...", which matches "openrouter/" only).
_API_KEY_ENV_BY_PREFIX: tuple[tuple[str, str], ...] = (
    ("gemini/", "GEMINI_API_KEY"),
    ("anthropic/", "ANTHROPIC_API_KEY"),
    ("openai/", "OPENAI_API_KEY"),
    ("openrouter/", "OPENROUTER_API_KEY"),
)


def resolve_api_key(target_model: str) -> str | None:
    """The API key litellm should use for `target_model`, resolved from its
    provider prefix against the matching env var. `None` when the prefix
    isn't one of the cloud providers above (a local ollama/ model needs no
    key) or the env var just isn't set — either way, the caller should
    simply omit `api_key` from its litellm.completion() kwargs rather than
    pass `None` through explicitly."""
    for prefix, env_var in _API_KEY_ENV_BY_PREFIX:
        if target_model.startswith(prefix):
            return os.getenv(env_var)
    return None


def get_cache_file() -> str:
    from sympose.bootstrap import resolve_workspace_dir

    ws = resolve_workspace_dir()
    os.makedirs(ws, exist_ok=True)
    return os.path.join(ws, ".models_cache.json")


def get_local_ollama_models() -> list[str]:
    """Live-queries a locally running Ollama for its actually-pulled model
    tags. A 0.5s timeout keeps this from stalling `/model` when Ollama isn't
    running at all — connection-refused on localhost is near-instant, this
    only guards the rare hung-daemon case. Never raises; empty list means
    "Ollama unreachable or nothing pulled," not an error to surface."""
    req = urllib.request.Request("http://localhost:11434/api/tags")
    try:
        with urllib.request.urlopen(req, timeout=0.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m["name"] for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


CACHE_TTL_SECONDS = 86400  # 24 hours


class ModelCatalog:
    """Manages cached model discovery from OpenRouter and local presets."""

    DEFAULT_RECOMMENDATIONS: ClassVar[list[dict[str, Any]]] = [
        {
            "id": "anthropic/claude-sonnet-4.5",
            "name": "Claude Sonnet 4.5",
            "context_length": 1_000_000,
            "desc": "Surgical coding & architecture",
        },
        {
            "id": "~anthropic/claude-sonnet-latest",
            "name": "Claude Sonnet (Latest)",
            "context_length": 1_000_000,
            "desc": "Auto-tracking latest Sonnet",
        },
        {
            "id": "deepseek/deepseek-v4-pro",
            "name": "DeepSeek V4 Pro",
            "context_length": 1_000_000,
            "desc": "Deep reasoning & fullstack",
        },
        {
            "id": "google/gemini-3.7-flash",
            "name": "Gemini 3.7 Flash",
            "context_length": 1_000_000,
            "desc": "Fast multimodal agentic worker",
        },
        {
            "id": "qwen/qwen3.8-27b",
            "name": "Qwen 3.8 27B",
            "context_length": 1_000_000,
            "desc": "High-density coding & tool calling",
        },
    ]

    @classmethod
    def get_cached_models(cls, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Loads models from local cache, or fetches from OpenRouter if expired/forced."""
        now = time.time()
        existing_cached_models = []
        cache_file = get_cache_file()

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                existing_cached_models = cached.get("models", [])
                if (
                    not force_refresh
                    and now - cached.get("timestamp", 0) < CACHE_TTL_SECONDS
                    and existing_cached_models
                ):
                    return existing_cached_models
            except Exception as e:
                log.debug("Failed to read model catalog cache %s: %s", cache_file, e)

        # Fetch fresh catalog if API key exists or public API is accessible
        fetched = cls.fetch_openrouter_catalog()
        if fetched:
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump({"timestamp": now, "models": fetched}, f)
            except Exception as e:
                log.debug("Failed to write model catalog cache %s: %s", cache_file, e)
            return fetched

        # Graceful fallback: return existing cached models (even if expired) or the
        # local recommendations list (no live catalog was ever fetchable).
        return existing_cached_models or list(cls.DEFAULT_RECOMMENDATIONS)

    @classmethod
    def fetch_openrouter_catalog(cls) -> list[dict[str, Any]]:
        """Fetches the live model catalog from OpenRouter with a short timeout."""
        api_key = os.getenv("OPENROUTER_API_KEY")
        headers = {"User-Agent": "Sympose-CLI"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models", headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models_raw = data.get("data", [])
                catalog = []
                for m in models_raw:
                    catalog.append(
                        {
                            "id": m.get("id", ""),
                            "name": m.get("name", m.get("id", "")),
                            "context_length": m.get("context_length", 0),
                            "description": (m.get("description") or "")[:120],
                        }
                    )
                return catalog
        except Exception:
            return []

    @classmethod
    def search_models(cls, query: str, limit: int = 8) -> list[dict[str, Any]]:
        """Searches cached OpenRouter catalog by substring query."""
        q = query.lower().strip()
        models = cls.get_cached_models()
        if not models:
            # Fallback to local default recommendations
            return [
                m
                for m in cls.DEFAULT_RECOMMENDATIONS
                if q in m["id"].lower() or q in m["name"].lower()
            ]

        matches = []
        for m in models:
            m_id = m.get("id", "")
            m_name = m.get("name", "")
            if q in m_id.lower() or q in m_name.lower():
                matches.append(m)
                if len(matches) >= limit:
                    break
        return matches

    @classmethod
    def get_completion_candidates(cls, prefix: str = "") -> list[str]:
        """Returns model slugs matching the prefix for tab auto-completion."""
        models = cls.get_cached_models()
        candidates = []
        p_clean = prefix.lower().replace("openrouter/", "")

        for m in models:
            m_id = m.get("id", "")
            if not p_clean or p_clean in m_id.lower():
                candidates.append(f"openrouter/{m_id}")
                if len(candidates) >= 25:
                    break

        return candidates
