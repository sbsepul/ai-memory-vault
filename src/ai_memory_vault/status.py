"""Cross-reference repos on disk against AI conversation history."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .config import DEFAULT_SEARCH_DEPTH, DEFAULT_SEARCH_DIRS, HOME
from .domain.models import Session
from .domain.status import StatusReport


def _find_git_repos(search_dirs: list[Path], max_depth: int) -> set[str]:
    repos: set[str] = set()
    for base in search_dirs:
        if not base.exists():
            continue
        result = subprocess.run(
            ["find", str(base), "-maxdepth", str(max_depth), "-name", ".git", "-type", "d"],
            capture_output=True,
            text=True,
        )
        for line in result.stdout.splitlines():
            rel = str(Path(line).parent.relative_to(HOME))
            repos.add(rel)
    return repos


def build_status(
    sessions: list[Session],
    search_dirs: list[Path] | None = None,
    max_depth: int = DEFAULT_SEARCH_DEPTH,
) -> StatusReport:
    if search_dirs is None:
        search_dirs = DEFAULT_SEARCH_DIRS

    disk_repos = _find_git_repos(search_dirs, max_depth)
    ai_paths = {s.project_rel_path for s in sessions}
    return StatusReport(disk_repos=disk_repos, ai_paths=ai_paths)
