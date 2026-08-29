"""
Session Archival, Flat-File JSONL Persistence & Resumption Engine for Sympose.
"""

import os
import json
import uuid
import datetime
from typing import Dict, List, Any, Optional
from sympose.bootstrap import resolve_workspace_dir


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
    def derive_title(cls, prompt: str) -> str:
        clean = prompt.strip().splitlines()[0] if prompt.strip() else "Untitled Session"
        clean = clean.replace('"', "'").strip()
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
                "title": title or cls.derive_title(user_message), "created_at": now_iso,
                "updated_at": now_iso, "turns_count": 0,
            }
            existing_lines = [json.dumps(meta)]

        if meta.get("turns_count", 0) == 0 and (meta.get("title") in ("New Conversation", "Untitled Session") or not meta.get("title")):
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
