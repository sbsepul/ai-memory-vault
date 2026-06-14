"""Extract sessions from Claude Code CLI (~/.claude/projects/)."""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .models import Message, Session


_HOME = Path.home()
_CLAUDE_PROJECTS = _HOME / ".claude" / "projects"


def _decode_project_path(slug: str) -> str:
    """
    Claude encodes the absolute path as a directory name by replacing '/' with '-'.
    e.g. '-home-alice-repos-dream-home' -> relative path 'repos/dream-home'
    We strip the home prefix and return a path relative to $HOME.
    """
    # The slug starts with '-home-<username>-' or '-Users-<username>-'
    abs_path = slug.replace("-", "/").lstrip("/")
    home_str = str(_HOME).lstrip("/")  # e.g. 'home/alice'
    if abs_path.startswith(home_str):
        rel = abs_path[len(home_str):].lstrip("/")
        return rel or "home"
    return abs_path


def _parse_message(event: dict) -> Message | None:
    msg_type = event.get("type")
    if msg_type == "user":
        content = event.get("message", {})
        if isinstance(content, dict):
            raw = content.get("content", "")
            if isinstance(raw, list):
                text = " ".join(
                    p.get("text", "") for p in raw if isinstance(p, dict) and p.get("type") == "text"
                )
            else:
                text = str(raw)
        else:
            text = str(content)
        ts_raw = event.get("timestamp")
        ts = datetime.fromisoformat(ts_raw) if ts_raw else None
        return Message(role="user", content=text.strip(), timestamp=ts)

    if msg_type == "assistant":
        content = event.get("message", {})
        if isinstance(content, dict):
            raw = content.get("content", "")
            if isinstance(raw, list):
                text = " ".join(
                    p.get("text", "") for p in raw if isinstance(p, dict) and p.get("type") == "text"
                )
            else:
                text = str(raw)
        else:
            text = str(content)
        ts_raw = event.get("timestamp")
        ts = datetime.fromisoformat(ts_raw) if ts_raw else None
        return Message(role="assistant", content=text.strip(), timestamp=ts)

    return None


def _parse_session_file(jsonl_path: Path, project_rel_path: str) -> Session | None:
    lines = []
    try:
        lines = jsonl_path.read_text(errors="replace").splitlines()
    except OSError:
        return None

    if not lines:
        return None

    messages: list[Message] = []
    started_at: datetime | None = None
    updated_at: datetime | None = None

    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue

        ts_raw = event.get("timestamp")
        ts = None
        if ts_raw:
            try:
                ts = datetime.fromisoformat(ts_raw)
            except ValueError:
                pass

        if ts:
            if started_at is None or ts < started_at:
                started_at = ts
            if updated_at is None or ts > updated_at:
                updated_at = ts

        msg = _parse_message(event)
        if msg:
            messages.append(msg)

    if not messages:
        return None

    session_id = jsonl_path.stem
    name = project_rel_path.split("/")[-1] if project_rel_path else session_id

    git_dir = (_HOME / project_rel_path / ".git") if project_rel_path else Path("/nonexistent")
    has_git = git_dir.exists()

    return Session(
        id=session_id,
        source="claude",
        project_rel_path=project_rel_path,
        name=name,
        started_at=started_at,
        updated_at=updated_at,
        messages=messages,
        has_git=has_git,
        original_abs_path=str(_HOME / project_rel_path),
    )


def extract_all(claude_dir: Path = _CLAUDE_PROJECTS) -> list[Session]:
    """Return all Claude Code sessions, each with a relative project path."""
    sessions: list[Session] = []

    if not claude_dir.exists():
        return sessions

    for project_dir in sorted(claude_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        rel_path = _decode_project_path(project_dir.name)
        for jsonl_file in sorted(project_dir.glob("*.jsonl")):
            session = _parse_session_file(jsonl_file, rel_path)
            if session:
                sessions.append(session)

    return sessions
