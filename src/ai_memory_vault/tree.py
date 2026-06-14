"""Build a project tree showing which directories have AI conversation history."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from .config import HOME
from .extractors.models import Session


@dataclass
class ProjectNode:
    rel_path: str
    has_git: bool = False
    path_exists: bool = False  # True if dir exists on disk even without .git
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
    """Return a flat map of rel_path -> ProjectNode, sorted by path."""
    nodes: dict[str, ProjectNode] = {}

    for s in sessions:
        path = s.project_rel_path or "(root)"
        if path not in nodes:
            nodes[path] = ProjectNode(
                rel_path=path,
                has_git=s.has_git,
                path_exists=(HOME / path).exists(),
            )
        node = nodes[path]
        node.has_git = node.has_git or s.has_git
        if s.source == "claude":
            node.claude_sessions += 1
            node.claude_messages += s.message_count
        else:
            node.codex_sessions += 1
            node.codex_messages += s.message_count

    return dict(sorted(nodes.items()))
