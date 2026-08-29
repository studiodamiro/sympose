"""
Session Archival, Flat-File JSONL Persistence & Milestone Titling for Sympose.
"""

import os
import re
import json
import uuid
import threading
import datetime
from typing import Dict, List, Any, Optional
from sympose.bootstrap import resolve_workspace_dir

GREETING_PATTERNS = [
    r"^(?:hi|hello|hey|yo|greetings|howdy|sup)\b",
    r"^(?:good\s+(?:morning|afternoon|evening|day))\b",
    r"^(?:quick\s+question|can\s+you\s+help|help\s+me|testing|test)\b",
]


class SessionManager:
    """Manages lightweight JSONL session archives with instant sub-millisecond local I/O."""

    @classmethod
    def get_sessions_dir(cls) -> str:
        s_dir = os.path.join(resolve_workspace_dir(), "sessions")
        os.makedirs(s_dir, exist_ok=True)
        return s_dir

    @classmethod
    def generate_session_id(cls, handle: str) -> str:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{handle.lower()}_{ts}_{uuid.uuid4().hex[:6]}"

    @classmethod
    def is_generic_prompt(cls, prompt: str) -> bool:
        clean = prompt.strip().lower()
        if len(clean) < 12: return True
        for pat in GREETING_PATTERNS:
            if re.search(pat, clean): return True
        return False

    @classmethod
    def derive_title(cls, prompt: str) -> str:
        clean = prompt.strip().splitlines()[0] if prompt.strip() else "Untitled Session"
        clean = clean.replace('"', "'").strip().rstrip(".:-")
        return (clean[:62].rsplit(" ", 1)[0] + "...") if len(clean) > 65 else (clean or "Untitled Session")

    @classmethod
    def format_relative_time(cls, dt_str: str) -> str:
        try:
            dt = datetime.datetime.fromisoformat(dt_str)
            now = datetime.datetime.now()
            if dt.date() == now.date(): return f"Today {dt.strftime('%H:%M')}"
            if dt.date() == now.date() - datetime.timedelta(days=1): return f"Yesterday {dt.strftime('%H:%M')}"
            return dt.strftime("%b %d, %H:%M" if dt.year == now.year else "%Y-%m-%d %H:%M")
        except Exception:
            return dt_str

    @classmethod
    def create_session(cls, handle: str, title: Optional[str] = None) -> Dict[str, Any]:
        session_id = cls.generate_session_id(handle)
        fpath = os.path.join(cls.get_sessions_dir(), f"{session_id}.jsonl")
        now_iso = datetime.datetime.now().isoformat()
        meta = {
            "type": "meta", "session_id": session_id, "handle": handle.lower(),
            "title": title or "New Conversation", "created_at": now_iso,
            "updated_at": now_iso, "turns_count": 0,
        }
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(json.dumps(meta) + "\n")
        return meta

    @classmethod
    def update_session_title(cls, session_id: str, title: str) -> bool:
        fpath = os.path.join(cls.get_sessions_dir(), f"{session_id}.jsonl")
        if not os.path.exists(fpath): return False
        clean_title = cls.derive_title(title)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
            if not lines: return False
            meta = json.loads(lines[0])
            if meta.get("type") == "meta":
                meta["title"] = clean_title
                meta["updated_at"] = datetime.datetime.now().isoformat()
                lines[0] = json.dumps(meta)
                with open(fpath, "w", encoding="utf-8") as f:
                    for l in lines: f.write(l + "\n")
                return True
        except Exception: return False
        return False

    @classmethod
    def generate_smart_title_async(cls, session_id: str, handle: str, turns: List[Dict[str, Any]], config: Any) -> None:
        def _worker():
            try:
                import litellm
                model = config.get("session.exit_behavior.summarization_model") or os.getenv("DEFAULT_MODEL", "gemini/gemini-3.6-flash")
                snippet = "\n".join(f"{'User' if 'user' in t else t.get('role', 'msg').capitalize()}: {t.get('user', t.get('content', ''))[:100]}" for t in turns[:4])
                prompt = f"Generate a concise 4-6 word headline topic for this conversation with @{handle}. Output ONLY the plain text headline without quotes or period:\n\n{snippet}"
                kwargs = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "timeout": 4.0, "max_tokens": 20}
                for pfx, key in (("gemini/", "GEMINI_API_KEY"), ("anthropic/", "ANTHROPIC_API_KEY"), ("openai/", "OPENAI_API_KEY"), ("openrouter/", "OPENROUTER_API_KEY")):
                    if model.startswith(pfx) and os.getenv(key): kwargs["api_key"] = os.getenv(key)
                resp = litellm.completion(**kwargs)
                out = (resp.choices[0].message.content or "").strip().strip('"\'').rstrip(".")
                if out and len(out) > 3 and not out.lower().startswith(("untitled", "none", "error")):
                    cls.update_session_title(session_id, out)
            except Exception: pass

        threading.Thread(target=_worker, daemon=True).start()

    @classmethod
    def append_turn(cls, session_id: str, handle: str, user_message: str, assistant_reply: str, title: Optional[str] = None) -> Optional[Dict[str, Any]]:
        fpath = os.path.join(cls.get_sessions_dir(), f"{session_id}.jsonl")
        now_iso = datetime.datetime.now().isoformat()
        meta, existing_lines = None, []
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    existing_lines = [l.strip() for l in f if l.strip()]
                if existing_lines:
                    first = json.loads(existing_lines[0])
                    if first.get("type") == "meta": meta = first
            except Exception: pass

        if not meta:
            meta = {
                "type": "meta", "session_id": session_id, "handle": handle.lower(),
                "title": title or ("New Conversation" if cls.is_generic_prompt(user_message) else cls.derive_title(user_message)),
                "created_at": now_iso, "updated_at": now_iso, "turns_count": 0,
            }
            existing_lines = [json.dumps(meta)]

        # If title is generic and current prompt is substantive, upgrade title
        if meta.get("title") in ("New Conversation", "Untitled Session") and not cls.is_generic_prompt(user_message):
            meta["title"] = title or cls.derive_title(user_message)

        meta["turns_count"] = meta.get("turns_count", 0) + 1
        meta["updated_at"] = now_iso
        existing_lines[0] = json.dumps(meta)

        turn_obj = {"type": "turn", "timestamp": now_iso, "user": user_message, "assistant": assistant_reply}
        with open(fpath, "w", encoding="utf-8") as f:
            for l in existing_lines: f.write(l + "\n")
            f.write(json.dumps(turn_obj) + "\n")
        return meta

    @classmethod
    def list_sessions(cls, handle: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        s_dir = cls.get_sessions_dir()
        if not os.path.exists(s_dir): return []
        results, h_low = [], handle.lower() if handle else None

        for fname in os.listdir(s_dir):
            if not fname.endswith(".jsonl"): continue
            try:
                with open(os.path.join(s_dir, fname), "r", encoding="utf-8") as f:
                    first = f.readline().strip()
                if not first: continue
                meta = json.loads(first)
                if meta.get("type") != "meta" or (h_low and meta.get("handle") != h_low): continue
                meta["relative_time"] = cls.format_relative_time(meta.get("updated_at", meta.get("created_at", "")))
                results.append(meta)
            except Exception: continue

        results.sort(key=lambda x: x.get("updated_at", x.get("created_at", "")), reverse=True)
        return results[:limit]

    @classmethod
    def load_session(cls, session_id: str) -> Optional[Dict[str, Any]]:
        fpath = os.path.join(cls.get_sessions_dir(), f"{session_id}.jsonl")
        if not os.path.exists(fpath): return None
        meta, turns = None, []
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    l = line.strip()
                    if not l: continue
                    obj = json.loads(l)
                    if obj.get("type") == "meta": meta = obj
                    elif obj.get("type") == "turn": turns.append(obj)
            if meta:
                meta["turns"] = turns
                meta["relative_time"] = cls.format_relative_time(meta.get("updated_at", meta.get("created_at", "")))
                return meta
        except Exception: return None
        return None

    @classmethod
    def delete_session(cls, session_id: str) -> bool:
        fpath = os.path.join(cls.get_sessions_dir(), f"{session_id}.jsonl")
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
                return True
            except Exception: return False
        return False
