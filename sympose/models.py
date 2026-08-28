"""
Model Discovery and OpenRouter Catalog Manager for Sympose.
Provides fast local caching, catalog search, and dynamic tab-completion candidates.
"""

import os
import json
import time
import urllib.request
from typing import List, Dict, Any, Optional

def get_cache_file() -> str:
    from sympose.bootstrap import resolve_workspace_dir
    ws = resolve_workspace_dir()
    os.makedirs(ws, exist_ok=True)
    return os.path.join(ws, ".models_cache.json")

CACHE_TTL_SECONDS = 86400  # 24 hours


class ModelCatalog:
    """Manages cached model discovery from OpenRouter and local presets."""

    DEFAULT_RECOMMENDATIONS = [
        {"id": "anthropic/claude-sonnet-4.5", "name": "Claude Sonnet 4.5", "context": "1M", "desc": "Surgical coding & architecture"},
        {"id": "~anthropic/claude-sonnet-latest", "name": "Claude Sonnet (Latest)", "context": "1M", "desc": "Auto-tracking latest Sonnet"},
        {"id": "deepseek/deepseek-v4-pro", "name": "DeepSeek V4 Pro", "context": "1M", "desc": "Deep reasoning & fullstack"},
        {"id": "google/gemini-3.7-flash", "name": "Gemini 3.7 Flash", "context": "1M", "desc": "Fast multimodal agentic worker"},
        {"id": "qwen/qwen3.8-27b", "name": "Qwen 3.8 27B", "context": "1M", "desc": "High-density coding & tool calling"},
    ]

    @classmethod
    def get_cached_models(cls, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Loads models from local cache, or fetches from OpenRouter if expired/forced."""
        now = time.time()
        existing_cached_models = []
        cache_file = get_cache_file()

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                existing_cached_models = cached.get("models", [])
                if not force_refresh and now - cached.get("timestamp", 0) < CACHE_TTL_SECONDS and existing_cached_models:
                    return existing_cached_models
            except Exception:
                pass

        # Fetch fresh catalog if API key exists or public API is accessible
        fetched = cls.fetch_openrouter_catalog()
        if fetched:
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump({"timestamp": now, "models": fetched}, f)
            except Exception:
                pass
            return fetched

        # Graceful fallback: return existing cached models (even if expired) or static catalog
        return existing_cached_models or list(cls.STATIC_CATALOG)

    @classmethod
    def fetch_openrouter_catalog(cls) -> List[Dict[str, Any]]:
        """Fetches the live model catalog from OpenRouter with a short timeout."""
        api_key = os.getenv("OPENROUTER_API_KEY")
        headers = {"User-Agent": "Sympose-CLI"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request("https://openrouter.ai/api/v1/models", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models_raw = data.get("data", [])
                catalog = []
                for m in models_raw:
                    catalog.append({
                        "id": m.get("id", ""),
                        "name": m.get("name", m.get("id", "")),
                        "context_length": m.get("context_length", 0),
                        "description": (m.get("description") or "")[:120],
                    })
                return catalog
        except Exception:
            return []

    @classmethod
    def search_models(cls, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        """Searches cached OpenRouter catalog by substring query."""
        q = query.lower().strip()
        models = cls.get_cached_models()
        if not models:
            # Fallback to local default recommendations
            return [m for m in cls.DEFAULT_RECOMMENDATIONS if q in m["id"].lower() or q in m["name"].lower()]

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
    def get_completion_candidates(cls, prefix: str = "") -> List[str]:
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
