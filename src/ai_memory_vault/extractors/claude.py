"""Extractor for Claude Code CLI (~/.claude/projects/)."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

from .models import BaseExtractor, Message, Session
from ..config import HOME, CLAUDE_PROJECTS_DIR
from ..utils import rel_path_from_cwd, parse_iso_timestamp, read_git_remote

# Files that are not conversation logs
_SKIP_NAMES = {"skill-injections.jsonl"}
_SKIP_DIRS  = {"vercel-plugin"}


def _rel_path_from_slug(slug: str) -> str:
    """Fallback: decode a Claude project directory slug to a relative path."""
    abs_path = slug.replace("-", "/").lstrip("/")
    home_str = str(HOME).lstrip("/")
    if abs_path.startswith(home_str):
        return abs_path[len(home_str):].lstrip("/") or "home"
    return abs_path


def _flatten_content(content) -> str:
    """Flatten any Claude content shape to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(p for p in parts if p)
    if isinstance(content, dict):
        inner = content.get("content", "")
        return _flatten_content(inner)
    return str(content)


def _parse_message(event: dict) -> Message | None:
    """Parse a standard Claude JSONL event into a Message."""
    msg_type = event.get("type")
    if msg_type not in ("user", "assistant"):
        return None
    text = _flatten_content(event.get("message", {}))
    ts = parse_iso_timestamp(event["timestamp"]) if event.get("timestamp") else None
    return Message(role=msg_type, content=text.strip(), timestamp=ts)


def _parse_session_file(jsonl_path: Path, slug_rel_path: str) -> Session | None:
    """Parse a standard Claude Code session JSONL."""
    try:
        lines = jsonl_path.read_text(errors="replace").splitlines()
    except OSError:
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

        msg = _parse_message(event)
        if msg and msg.content:
            messages.append(msg)

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


def _parse_subagent_file(jsonl_path: Path, slug_rel_path: str) -> Session | None:
    """Parse a Claude subagent JSONL (nested under {session_id}/subagents/)."""
    try:
        lines = jsonl_path.read_text(errors="replace").splitlines()
    except OSError:
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

        event_type = event.get("type")
        if event_type not in ("user", "assistant"):
            continue

        ts = parse_iso_timestamp(event.get("timestamp")) if event.get("timestamp") else None
        if ts:
            if started_at is None or ts < started_at:
                started_at = ts
            if updated_at is None or ts > updated_at:
                updated_at = ts

        raw_msg = event.get("message", "")
        text = _flatten_content(raw_msg)
        if text.strip():
            messages.append(Message(role=event_type, content=text.strip(), timestamp=ts))

    if not messages:
        return None

    has_git = (HOME / slug_rel_path / ".git").exists()

    return Session(
        id=jsonl_path.stem,
        source="claude",
        project_rel_path=slug_rel_path,
        name=f"subagent · {slug_rel_path.split('/')[-1]}",
        started_at=started_at,
        updated_at=updated_at,
        messages=messages,
        has_git=has_git,
    )


class ClaudeExtractor(BaseExtractor):
    label = "Claude Code"
    source = "claude"

    def __init__(self, claude_dir: Path = CLAUDE_PROJECTS_DIR) -> None:
        self._dir = claude_dir

    def is_available(self) -> bool:
        return self._dir.exists()

    def extract_all(self) -> list[Session]:
        sessions: list[Session] = []

        if not self._dir.exists():
            return sessions

        for project_dir in sorted(self._dir.iterdir()):
            if not project_dir.is_dir():
                continue

            slug_fallback = _rel_path_from_slug(project_dir.name)

            for jsonl_file in sorted(project_dir.rglob("*.jsonl")):
                if jsonl_file.name in _SKIP_NAMES:
                    continue
                if any(part in _SKIP_DIRS for part in jsonl_file.parts):
                    continue

                rel = jsonl_file.relative_to(project_dir)
                if len(rel.parts) == 1:
                    session = _parse_session_file(jsonl_file, slug_fallback)
                else:
                    session = _parse_subagent_file(jsonl_file, slug_fallback)

                if session:
                    sessions.append(session)

        return sessions


# Module-level convenience kept for backwards compatibility
def extract_all(claude_dir: Path = CLAUDE_PROJECTS_DIR) -> list[Session]:
    return ClaudeExtractor(claude_dir).extract_all()
