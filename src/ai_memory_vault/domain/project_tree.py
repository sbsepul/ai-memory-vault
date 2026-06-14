"""Project-level aggregation helpers."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import HOME
from .models import Session


@dataclass
class ProjectNode:
    rel_path: str
    has_git: bool = False
    path_exists: bool = False
    claude_sessions: int = 0
    codex_sessions: int = 0
    claude_messages: int = 0
    codex_messages: int = 0

    @property
    def total_sessions(self) -> int:
        return self.claude_sessions + self.codex_sessions

    @property
    def total_messages(self) -> int:
        return self.claude_messages + self.codex_messages


def build_tree(sessions: list[Session]) -> dict[str, ProjectNode]:
    nodes: dict[str, ProjectNode] = {}

    for session in sessions:
        path = session.project_rel_path or "(root)"
        node = nodes.setdefault(
            path,
            ProjectNode(
                rel_path=path,
                has_git=session.has_git,
                path_exists=(HOME / path).exists(),
            ),
        )
        node.has_git = node.has_git or session.has_git
        if session.source == "claude":
            node.claude_sessions += 1
            node.claude_messages += session.message_count
        else:
            node.codex_sessions += 1
            node.codex_messages += session.message_count

    return dict(sorted(nodes.items()))
