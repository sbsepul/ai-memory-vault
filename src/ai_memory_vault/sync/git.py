"""Backward-compatible vault sync import path."""

from ..infrastructure.sync.git import (
    PullResult,
    _clone_repos,
    _write_repo_manifest,
    backup_raw_claude,
    backup_raw_sessions,
    load_config,
    pull_from_vault,
    push_to_vault,
    restore_raw_claude,
    restore_raw_sessions,
    save_config,
)

__all__ = [
    "PullResult",
    "backup_raw_claude",
    "backup_raw_sessions",
    "load_config",
    "pull_from_vault",
    "push_to_vault",
    "restore_raw_claude",
    "restore_raw_sessions",
    "save_config",
    "_write_repo_manifest",
    "_clone_repos",
]
