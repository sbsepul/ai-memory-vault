"""Export sessions to Markdown files organized by relative project path."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime

from ..extractors.models import Session


def _fmt_ts(ts: datetime | None) -> str:
    if ts is None:
        return "unknown"
    return ts.strftime("%Y-%m-%d %H:%M UTC")


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

    for msg in session.messages:
        if msg.role == "user":
            lines.append("**User**")
        elif msg.role == "assistant":
            lines.append("**Assistant**")
        else:
            lines.append(f"**{msg.role.capitalize()}**")

        if msg.timestamp:
            lines.append(f"*{_fmt_ts(msg.timestamp)}*")
        lines.append("")
        lines.append(msg.content)
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def export_sessions(sessions: list[Session], output_dir: Path) -> list[Path]:
    """
    Write each session as a .md file under output_dir/{source}/{project_rel_path}/.
    Returns list of files written.
    """
    written: list[Path] = []
    for session in sessions:
        # Build directory: output_dir/claude/work/project/ or output_dir/codex/work/project/
        project_dir = output_dir / session.source / session.project_rel_path
        project_dir.mkdir(parents=True, exist_ok=True)

        ts_prefix = session.started_at.strftime("%Y%m%d-%H%M") if session.started_at else "unknown"
        filename = f"{ts_prefix}_{session.id[:8]}.md"
        dest = project_dir / filename

        dest.write_text(_session_to_markdown(session), encoding="utf-8")
        written.append(dest)

    return written
