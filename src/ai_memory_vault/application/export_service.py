"""Application helpers for exports."""

from __future__ import annotations

from ..domain.models import Session


def sessions_to_json_ready(sessions: list[Session]) -> list[dict]:
    return [
        {
            "id": session.id,
            "source": session.source,
            "project_rel_path": session.project_rel_path,
            "name": session.name,
            "has_git": session.has_git,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                    "timestamp": message.timestamp.isoformat() if message.timestamp else None,
                }
                for message in session.messages
            ],
        }
        for session in sessions
    ]
