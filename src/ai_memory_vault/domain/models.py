"""Shared session domain models."""

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
    source: str
    project_rel_path: str
    name: str
    started_at: datetime | None
    updated_at: datetime | None
    messages: list[Message] = field(default_factory=list)
    has_git: bool = False

    @property
    def message_count(self) -> int:
        return sum(1 for message in self.messages if message.role in ("user", "assistant"))
