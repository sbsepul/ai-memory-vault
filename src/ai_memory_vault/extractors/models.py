"""Shared data models for extracted sessions."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class Message:
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: datetime | None = None


@dataclass
class Session:
    """Normalized session from any supported AI tool."""
    id: str
    # Source identifier — "claude", "codex", or any future tool name
    source: str
    # Relative path from $HOME, e.g. "work/my-company/backend"
    project_rel_path: str
    # Human-readable name (thread_name for Codex, last dir component for Claude)
    name: str
    started_at: datetime | None
    updated_at: datetime | None
    messages: list[Message] = field(default_factory=list)
    # True if the project directory currently exists as a git repo
    has_git: bool = False

    @property
    def message_count(self) -> int:
        return len([m for m in self.messages if m.role in ("user", "assistant")])
