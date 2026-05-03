import json

from fastapi import APIRouter

from database.sqlite import db

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/history")
def get_chat_history(limit: int = 50):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_sessions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()

    sessions = []
    for r in rows:
        s = dict(r)
        for key in ("sources", "context_used"):
            try:
                s[key] = json.loads(s.get(key) or "[]")
            except (json.JSONDecodeError, TypeError):
                s[key] = []
        sessions.append(s)
    return sessions
