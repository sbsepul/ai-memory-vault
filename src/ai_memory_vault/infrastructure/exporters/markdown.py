"""Export sessions to Markdown files organized by relative project path."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ...domain.models import Session


def _fmt_ts(ts: datetime | None) -> str:
    return ts.strftime("%Y-%m-%d %H:%M UTC") if ts else "unknown"


def _session_to_markdown(session: Session) -> str:
    lines = [
        f"# {session.name}",
        "",
        f"- **Source**: {session.source}",
        f"- **Session ID**: `{session.id}`",
        f"- **Project**: `{session.project_rel_path}`",
        f"- **Git repo**: {'yes' if session.has_git else 'no'}",
        f"- **Started**: {_fmt_ts(session.started_at)}",
        f"- **Last updated**: {_fmt_ts(session.updated_at)}",
        f"- **Messages**: {session.message_count}",
        "",
        "---",
        "",
    ]

    for message in session.messages:
        if message.role == "user":
            lines.append("**User**")
        elif message.role == "assistant":
            lines.append("**Assistant**")
        else:
            lines.append(f"**{message.role.capitalize()}**")
        if message.timestamp:
            lines.append(f"*{_fmt_ts(message.timestamp)}*")
        lines.append("")
        lines.append(message.content)
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def export_sessions(sessions: list[Session], output_dir: Path) -> list[Path]:
    written: list[Path] = []
    for session in sessions:
        project_dir = output_dir / session.source / session.project_rel_path
        project_dir.mkdir(parents=True, exist_ok=True)

        ts_prefix = session.started_at.strftime("%Y%m%d-%H%M") if session.started_at else "unknown"
        destination = project_dir / f"{ts_prefix}_{session.id[:8]}.md"
        destination.write_text(_session_to_markdown(session), encoding="utf-8")
        written.append(destination)

    return written
