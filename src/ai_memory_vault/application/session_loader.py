"""Application service for loading and filtering sessions."""

from __future__ import annotations

from datetime import datetime, timezone

from rich.console import Console

from ..agents import AGENTS
from ..config import HOME
from ..domain.models import Session
from ..resolver import apply_path_map, load_path_map


class SessionLoader:
    """Central entry point for session retrieval, normalization, and filtering."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def load(self, source: str = "all", since: str | None = None) -> list[Session]:
        sessions: list[Session] = []

        for adapter in AGENTS.select([source]):
            with self.console.status(f"[bold {adapter.color}]Reading {adapter.label} sessions…"):
                sessions.extend(adapter.extract_sessions())

        sessions = self._apply_saved_path_map(sessions)
        sessions = self._resolve_to_git_root(sessions)

        if since:
            sessions = self._filter_since(sessions, since)

        return sessions

    def filter_by_project(self, sessions: list[Session], project: str | None) -> list[Session]:
        if not project:
            return sessions
        needle = project.lower()
        return [session for session in sessions if needle in session.project_rel_path.lower()]

    def _apply_saved_path_map(self, sessions: list[Session]) -> list[Session]:
        path_map = load_path_map()
        if not path_map:
            return sessions

        for session in sessions:
            canonical = apply_path_map(session.project_rel_path, path_map)
            if canonical != session.project_rel_path:
                session.project_rel_path = canonical
                session.has_git = (HOME / canonical / ".git").exists()
        return sessions

    def _resolve_to_git_root(self, sessions: list[Session]) -> list[Session]:
        for session in sessions:
            if session.has_git:
                continue
            full = HOME / session.project_rel_path
            if not full.exists():
                continue
            current = full.parent
            while current != HOME and current != current.parent:
                if (current / ".git").exists():
                    session.project_rel_path = str(current.relative_to(HOME))
                    session.has_git = True
                    break
                current = current.parent
        return sessions

    def _filter_since(self, sessions: list[Session], since: str) -> list[Session]:
        try:
            cutoff = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
        except ValueError:
            self.console.print(
                f"[yellow]Warning: invalid --since date '{since}', ignored.[/yellow]"
            )
            return sessions

        return [
            session
            for session in sessions
            if session.updated_at and session.updated_at.replace(tzinfo=timezone.utc) >= cutoff
        ]
