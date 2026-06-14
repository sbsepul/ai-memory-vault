"""Extract sessions from Claude Code CLI (~/.claude/projects/)."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

from .models import Message, Session


_HOME = Path.home()
_CLAUDE_PROJECTS = _HOME / ".claude" / "projects"


def _rel_path_from_cwd(cwd: str) -> str:
    """Strip $HOME prefix to get a portable relative path."""
    home_str = str(_HOME)
    if cwd.startswith(home_str):
        return cwd[len(home_str):].lstrip("/") or "home"
    return cwd.lstrip("/")


def _rel_path_from_slug(slug: str) -> str:
    """
    Fallback: decode the Claude project directory slug when no cwd is found in
    the session file. Claude encodes '/' as '-', so this is ambiguous for
    directory names that contain hyphens — prefer cwd when available.
    e.g. '-home-alice-repos-dream-home' -> 'repos/dream-home'
    """
    abs_path = slug.replace("-", "/").lstrip("/")
    home_str = str(_HOME).lstrip("/")
    if abs_path.startswith(home_str):
        return abs_path[len(home_str):].lstrip("/") or "home"
    return abs_path


def _parse_message(event: dict) -> Message | None:
    msg_type = event.get("type")
    if msg_type == "user":
        content = event.get("message", {})
        if isinstance(content, dict):
            raw = content.get("content", "")
            if isinstance(raw, list):
                text = " ".join(
                    p.get("text", "") for p in raw
                    if isinstance(p, dict) and p.get("type") == "text"
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
                    p.get("text", "") for p in raw
                    if isinstance(p, dict) and p.get("type") == "text"
                )
            else:
                text = str(raw)
        else:
            text = str(content)
        ts_raw = event.get("timestamp")
        ts = datetime.fromisoformat(ts_raw) if ts_raw else None
        return Message(role="assistant", content=text.strip(), timestamp=ts)

    return None


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
    cwd_rel_path: str | None = None  # set from the first event that has cwd

    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue

        # Use the first cwd we find as the authoritative project path.
        # This avoids the ambiguity in slug decoding (hyphens vs slashes).
        if cwd_rel_path is None:
            raw_cwd = event.get("cwd")
            if raw_cwd:
                cwd_rel_path = _rel_path_from_cwd(raw_cwd)

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

    # cwd from events is authoritative; slug decoding is the fallback
    project_rel_path = cwd_rel_path or slug_rel_path
    name = project_rel_path.split("/")[-1] if project_rel_path else jsonl_path.stem
    git_dir = _HOME / project_rel_path / ".git"
    has_git = git_dir.exists()

    return Session(
        id=jsonl_path.stem,
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
    """Return all Claude Code sessions with accurate relative project paths."""
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
