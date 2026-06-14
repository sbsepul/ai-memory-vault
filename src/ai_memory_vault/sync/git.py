"""Backward-compatible vault sync import path."""

from ..infrastructure.sync.git import (
    PullResult,
    backup_raw_claude,
    load_config,
    pull_from_vault,
    push_to_vault,
    restore_raw_claude,
    save_config,
)

__all__ = [
    "PullResult",
    "backup_raw_claude",
    "load_config",
    "pull_from_vault",
    "push_to_vault",
    "restore_raw_claude",
    "save_config",
]
