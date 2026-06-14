"""Status report domain model."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Session


@dataclass
class StatusReport:
    disk_repos: set[str]
    ai_paths: set[str]

    @property
    def with_history(self) -> set[str]:
        return self.disk_repos & self.ai_paths

    @property
    def no_history(self) -> set[str]:
        return self.disk_repos - self.ai_paths

    @property
    def orphan(self) -> set[str]:
        return self.ai_paths - self.disk_repos

    @property
    def orphan_exists_no_git(self) -> set[str]:
        from ..config import HOME

        result = set()
        for path in self.orphan:
            full = HOME / path
            if full.exists() and not (full / ".git").exists():
                if any(repo.startswith(path + "/") for repo in self.disk_repos):
                    continue
                if any(other.startswith(path + "/") for other in self.orphan if other != path):
                    continue
                result.add(path)
        return result

    @property
    def orphan_missing(self) -> set[str]:
        from ..config import HOME

        return {path for path in self.orphan if not (HOME / path).exists()}

    def orphan_stats(self, sessions: list[Session]) -> dict[str, tuple[int, int]]:
        return _session_stats(self.orphan, sessions)

    def with_history_stats(self, sessions: list[Session]) -> dict[str, tuple[int, int]]:
        return _session_stats(self.with_history, sessions)


def _session_stats(paths: set[str], sessions: list[Session]) -> dict[str, tuple[int, int]]:
    stats: dict[str, tuple[int, int]] = {}
    for path in paths:
        matched = [session for session in sessions if session.project_rel_path == path]
        stats[path] = (len(matched), sum(session.message_count for session in matched))
    return stats
