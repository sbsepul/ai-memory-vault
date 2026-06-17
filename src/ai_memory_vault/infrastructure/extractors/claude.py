"""Extract sessions from Claude Code CLI (~/.claude/projects/)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ...config import CLAUDE_PROJECTS_DIR, HOME
from ...domain.models import Message, Session
from ...utils import parse_iso_timestamp, read_git_remote, rel_path_from_cwd


def _rel_path_from_slug(slug: str) -> str:
    abs_path = slug.replace("-", "/").lstrip("/")
    home_str = str(HOME).lstrip("/")
    if abs_path.startswith(home_str):
        return abs_path[len(home_str) :].lstrip("/") or "home"
    return abs_path


def _extract_text(content: object) -> str:
    if isinstance(content, dict):
        raw = content.get("content", "")
        if isinstance(raw, list):
            return " ".join(
                part.get("text", "")
                for part in raw
                if isinstance(part, dict) and part.get("type") == "text"
            )
        return str(raw)
    return str(content)


def _parse_message(event: dict) -> Message | None:
    msg_type = event.get("type")
    if msg_type not in ("user", "assistant"):
        return None

    ts = parse_iso_timestamp(event["timestamp"]) if event.get("timestamp") else None
    return Message(
        role=msg_type,
        content=_extract_text(event.get("message", {})).strip(),
        timestamp=ts,
    )


def _parse_session_file(jsonl_path: Path, slug_rel_path: str) -> Session | None:
    try:
        lines = jsonl_path.read_text(errors="replace").splitlines()
    except OSError:
        return None

    if not lines:
        return None

    messages: list[Message] = []
    started_at: datetime | None = None
    updated_at: datetime | None = None
    cwd_rel_path: str | None = None

    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if cwd_rel_path is None:
            raw_cwd = event.get("cwd")
            if raw_cwd:
                cwd_rel_path = rel_path_from_cwd(raw_cwd)

        ts = parse_iso_timestamp(event["timestamp"]) if event.get("timestamp") else None
        if ts:
            if started_at is None or ts < started_at:
                started_at = ts
            if updated_at is None or ts > updated_at:
                updated_at = ts

        message = _parse_message(event)
        if message:
            messages.append(message)

    if not messages:
        return None

    project_rel_path = cwd_rel_path or slug_rel_path
    name = project_rel_path.split("/")[-1] if project_rel_path else jsonl_path.stem
    project_dir = HOME / project_rel_path
    has_git = (project_dir / ".git").exists()

    return Session(
        id=jsonl_path.stem,
        source="claude",
        project_rel_path=project_rel_path,
        name=name,
        started_at=started_at,
        updated_at=updated_at,
        messages=messages,
        has_git=has_git,
        git_remote=read_git_remote(project_dir) if has_git else None,
    )


def extract_all(claude_dir: Path = CLAUDE_PROJECTS_DIR) -> list[Session]:
    sessions: list[Session] = []
    if not claude_dir.exists():
        return sessions

    for project_dir in sorted(claude_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        slug_fallback = _rel_path_from_slug(project_dir.name)
        for jsonl_file in sorted(project_dir.glob("*.jsonl")):
            session = _parse_session_file(jsonl_file, slug_fallback)
            if session:
                sessions.append(session)
    return sessions
