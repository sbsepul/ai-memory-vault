"""Project endpoints: GET /api/projects."""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Query

from .._loader import get_all_sessions

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
def list_projects(source: Optional[str] = Query(None)):
    sessions = get_all_sessions()
    if source:
        sessions = [s for s in sessions if s.source == source]

    projects: dict[str, dict] = {}
    for s in sessions:
        p = s.project_rel_path
        if p not in projects:
            projects[p] = {
                "path": p,
                "name": p.split("/")[-1] if p else p,
                "has_git": s.has_git,
                "sources": {},
                "total_sessions": 0,
                "total_messages": 0,
                "last_active": None,
            }
        proj = projects[p]
        proj["sources"][s.source] = proj["sources"].get(s.source, 0) + 1
        proj["total_sessions"] += 1
        proj["total_messages"] += s.message_count
        if s.updated_at:
            iso = s.updated_at.isoformat()
            if proj["last_active"] is None or iso > proj["last_active"]:
                proj["last_active"] = iso

    return sorted(projects.values(), key=lambda p: p["last_active"] or "", reverse=True)
