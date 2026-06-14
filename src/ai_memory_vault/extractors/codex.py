"""Extract sessions from Codex CLI (~/.codex/sessions/)."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

from .models import Message, Session


_HOME = Path.home()
_CODEX_DIR = _HOME / ".codex"
_SESSIONS_DIR = _CODEX_DIR / "sessions"
_SESSION_INDEX = _CODEX_DIR / "session_index.jsonl"


def _rel_path_from_cwd(cwd: str) -> str:
    """Strip $HOME prefix to get a portable relative path."""
    home_str = str(_HOME)
    if cwd.startswith(home_str):
        rel = cwd[len(home_str):].lstrip("/")
        return rel or "home"
    # Outside home: keep as-is but strip leading slash
    return cwd.lstrip("/")


def _load_thread_names() -> dict[str, str]:
    """Build id → thread_name map from session_index.jsonl."""
    names: dict[str, str] = {}
    if not _SESSION_INDEX.exists():
        return names
    for line in _SESSION_INDEX.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            tid = entry.get("id")
            name = entry.get("thread_name", "")
            if tid and name:
                names[tid] = name
        except json.JSONDecodeError:
            continue
    return names


def _parse_content(content) -> str:
    """Flatten Codex content field to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif item.get("type") == "tool_result":
                    inner = item.get("content", "")
                    parts.append(_parse_content(inner))
        return "\n".join(p for p in parts if p)
    return ""


def _parse_session_file(
    jsonl_path: Path,
    thread_names: dict[str, str],
) -> Session | None:
    try:
        raw_lines = jsonl_path.read_text(errors="replace").splitlines()
    except OSError:
        return None

    if not raw_lines:
        return None

    session_id: str | None = None
    project_rel_path: str = ""
    thread_name: str = ""
    messages: list[Message] = []
    started_at: datetime | None = None
    updated_at: datetime | None = None

    for raw in raw_lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue

        # Timestamp from the envelope
        ts_raw = event.get("timestamp")
        ts: datetime | None = None
        if ts_raw:
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                pass

        if ts:
            if started_at is None or ts < started_at:
                started_at = ts
            if updated_at is None or ts > updated_at:
                updated_at = ts

        event_type = event.get("type")
        payload = event.get("payload", {})

        # First event carries session metadata
        if event_type == "session_meta" and not session_id:
            session_id = payload.get("id") or event.get("id")
            cwd = payload.get("cwd", "")
            if cwd:
                project_rel_path = _rel_path_from_cwd(cwd)
            if session_id:
                thread_name = thread_names.get(session_id, "")

        # Codex wraps all messages inside event_msg with a payload.type discriminator
        elif event_type == "event_msg":
            sub = payload.get("type", "")

            if sub == "user_message":
                text = payload.get("message", "")
                if isinstance(text, list):
                    text = _parse_content(text)
                if text and str(text).strip():
                    messages.append(Message(role="user", content=str(text).strip(), timestamp=ts))

            elif sub == "agent_message":
                text = payload.get("message", "")
                if text and str(text).strip():
                    messages.append(Message(role="assistant", content=str(text).strip(), timestamp=ts))

            elif sub == "task_complete":
                # Final summary message from the agent
                text = payload.get("last_agent_message", "")
                if text and str(text).strip() and messages and messages[-1].role != "assistant":
                    messages.append(Message(role="assistant", content=str(text).strip(), timestamp=ts))

    if not messages or not session_id:
        return None

    name = thread_name or (project_rel_path.split("/")[-1] if project_rel_path else session_id)
    git_dir = (_HOME / project_rel_path / ".git") if project_rel_path else Path("/nonexistent")
    has_git = git_dir.exists()

    return Session(
        id=session_id,
        source="codex",
        project_rel_path=project_rel_path,
        name=name,
        started_at=started_at,
        updated_at=updated_at,
        messages=messages,
        has_git=has_git,
        original_abs_path=str(_HOME / project_rel_path) if project_rel_path else "",
    )


def extract_all(sessions_dir: Path = _SESSIONS_DIR) -> list[Session]:
    """Return all Codex sessions with relative project paths."""
    thread_names = _load_thread_names()
    sessions: list[Session] = []

    if not sessions_dir.exists():
        return sessions

    for jsonl_file in sorted(sessions_dir.rglob("*.jsonl")):
        session = _parse_session_file(jsonl_file, thread_names)
        if session:
            sessions.append(session)

    return sessions
