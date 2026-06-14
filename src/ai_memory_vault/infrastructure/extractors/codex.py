"""Extract sessions from Codex CLI (~/.codex/sessions/)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ...config import CODEX_SESSION_INDEX, CODEX_SESSIONS_DIR, HOME
from ...domain.models import Message, Session
from ...utils import parse_iso_timestamp, rel_path_from_cwd


def _load_thread_names() -> dict[str, str]:
    names: dict[str, str] = {}
    if not CODEX_SESSION_INDEX.exists():
        return names
    for line in CODEX_SESSION_INDEX.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        thread_id = entry.get("id")
        name = entry.get("thread_name", "")
        if thread_id and name:
            names[thread_id] = name
    return names


def _parse_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif item.get("type") == "tool_result":
                    parts.append(_parse_content(item.get("content", "")))
        return "\n".join(part for part in parts if part)
    return ""


def _parse_session_file(jsonl_path: Path, thread_names: dict[str, str]) -> Session | None:
    try:
        raw_lines = jsonl_path.read_text(errors="replace").splitlines()
    except OSError:
        return None

    if not raw_lines:
        return None

    session_id: str | None = None
    project_rel_path = ""
    thread_name = ""
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

        ts = parse_iso_timestamp(event["timestamp"]) if event.get("timestamp") else None
        if ts:
            if started_at is None or ts < started_at:
                started_at = ts
            if updated_at is None or ts > updated_at:
                updated_at = ts

        event_type = event.get("type")
        payload = event.get("payload", {})

        if event_type == "session_meta" and not session_id:
            session_id = payload.get("id") or event.get("id")
            cwd = payload.get("cwd", "")
            if cwd:
                project_rel_path = rel_path_from_cwd(cwd)
            if session_id:
                thread_name = thread_names.get(session_id, "")
        elif event_type == "event_msg":
            sub_type = payload.get("type", "")
            if sub_type == "user_message":
                text = payload.get("message", "")
                if isinstance(text, list):
                    text = _parse_content(text)
                if text and str(text).strip():
                    messages.append(Message(role="user", content=str(text).strip(), timestamp=ts))
            elif sub_type == "agent_message":
                text = payload.get("message", "")
                if text and str(text).strip():
                    messages.append(
                        Message(role="assistant", content=str(text).strip(), timestamp=ts)
                    )
            elif sub_type == "task_complete":
                text = payload.get("last_agent_message", "")
                if text and str(text).strip() and messages and messages[-1].role != "assistant":
                    messages.append(
                        Message(role="assistant", content=str(text).strip(), timestamp=ts)
                    )

    if not messages or not session_id:
        return None

    name = thread_name or (project_rel_path.split("/")[-1] if project_rel_path else session_id)
    has_git = (HOME / project_rel_path / ".git").exists() if project_rel_path else False

    return Session(
        id=session_id,
        source="codex",
        project_rel_path=project_rel_path,
        name=name,
        started_at=started_at,
        updated_at=updated_at,
        messages=messages,
        has_git=has_git,
    )


def extract_all(sessions_dir: Path = CODEX_SESSIONS_DIR) -> list[Session]:
    thread_names = _load_thread_names()
    sessions: list[Session] = []
    if not sessions_dir.exists():
        return sessions

    for jsonl_file in sorted(sessions_dir.rglob("*.jsonl")):
        session = _parse_session_file(jsonl_file, thread_names)
        if session:
            sessions.append(session)
    return sessions
