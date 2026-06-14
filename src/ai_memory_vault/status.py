"""Cross-reference repos on disk against AI conversation history."""
from __future__ import annotations
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .extractors.models import Session

_HOME = Path.home()


def _find_git_repos(search_dirs: list[Path], max_depth: int = 5) -> set[str]:
    repos: set[str] = set()
    for base in search_dirs:
        if not base.exists():
            continue
        result = subprocess.run(
            ["find", str(base), "-maxdepth", str(max_depth),
             "-name", ".git", "-type", "d"],
            capture_output=True, text=True,
        )
        for line in result.stdout.splitlines():
            rel = str(Path(line).parent.relative_to(_HOME))
            repos.add(rel)
    return repos


@dataclass
class StatusReport:
    disk_repos: set[str]
    ai_paths: set[str]

    @property
    def with_history(self) -> set[str]:
        """Repos on disk that also have AI history."""
        return self.disk_repos & self.ai_paths

    @property
    def no_history(self) -> set[str]:
        """Repos on disk with zero AI history."""
        return self.disk_repos - self.ai_paths

    @property
    def orphan(self) -> set[str]:
        """AI history pointing to paths that no longer exist on disk."""
        return self.ai_paths - self.disk_repos

    def orphan_stats(self, sessions: list[Session]) -> dict[str, tuple[int, int]]:
        """Return {rel_path: (n_sessions, n_messages)} for orphan paths."""
        stats: dict[str, tuple[int, int]] = {}
        for path in self.orphan:
            matched = [s for s in sessions if s.project_rel_path == path]
            stats[path] = (len(matched), sum(s.message_count for s in matched))
        return stats

    def with_history_stats(self, sessions: list[Session]) -> dict[str, tuple[int, int]]:
        stats: dict[str, tuple[int, int]] = {}
        for path in self.with_history:
            matched = [s for s in sessions if s.project_rel_path == path]
            stats[path] = (len(matched), sum(s.message_count for s in matched))
        return stats


def build_status(
    sessions: list[Session],
    search_dirs: list[Path] | None = None,
    max_depth: int = 5,
) -> StatusReport:
    if search_dirs is None:
        search_dirs = [_HOME / "repos", _HOME / "work"]

    disk_repos = _find_git_repos(search_dirs, max_depth)
    ai_paths = {s.project_rel_path for s in sessions}
    return StatusReport(disk_repos=disk_repos, ai_paths=ai_paths)
