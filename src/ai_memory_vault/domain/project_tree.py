"""Project-level aggregation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import HOME
from .models import Session


@dataclass
class SourceStats:
    sessions: int = 0
    messages: int = 0


@dataclass
class ProjectNode:
    rel_path: str
    has_git: bool = False
    path_exists: bool = False
    sources: dict[str, SourceStats] = field(default_factory=dict)

    @property
    def total_sessions(self) -> int:
        return sum(stats.sessions for stats in self.sources.values())

    @property
    def total_messages(self) -> int:
        return sum(stats.messages for stats in self.sources.values())

    def stats_for(self, source: str) -> SourceStats:
        return self.sources.get(source, SourceStats())


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
        stats = node.sources.setdefault(session.source, SourceStats())
        stats.sessions += 1
        stats.messages += session.message_count

    return dict(sorted(nodes.items()))
