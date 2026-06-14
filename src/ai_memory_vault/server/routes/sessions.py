"""Session endpoints: GET /api/sessions, GET /api/sessions/{id}."""
from __future__ import annotations
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from .._loader import get_all_sessions

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

_EPOCH = datetime.min


def _to_dict(s, *, include_messages: bool = False) -> dict:
    d = {
        "id": s.id,
        "source": s.source,
        "project": s.project_rel_path,
        "name": s.name,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        "message_count": s.message_count,
        "has_git": s.has_git,
    }
    if include_messages:
        d["messages"] = [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
            }
            for m in s.messages
            if m.role in ("user", "assistant")
        ]
    return d


@router.get("")
def list_sessions(
    source: Optional[str] = Query(None),
    project: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
):
    sessions = get_all_sessions()
    if source:
        sessions = [s for s in sessions if s.source == source]
    if project:
        sessions = [s for s in sessions if s.project_rel_path == project]
    sessions = sorted(sessions, key=lambda s: s.updated_at or _EPOCH, reverse=True)
    return [_to_dict(s) for s in sessions[:limit]]


@router.get("/{session_id}")
def get_session(session_id: str):
    for s in get_all_sessions():
        if s.id == session_id:
            return _to_dict(s, include_messages=True)
    raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
