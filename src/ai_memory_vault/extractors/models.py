"""Shared data models and base extractor for all supported AI tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
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
    source: str  # "claude", "codex", or any future tool slug
    project_rel_path: str  # relative to $HOME, e.g. "work/my-company/backend"
    name: str
    started_at: datetime | None
    updated_at: datetime | None
    messages: list[Message] = field(default_factory=list)
    has_git: bool = False
    git_remote: str | None = None

    @property
    def message_count(self) -> int:
        return len([m for m in self.messages if m.role in ("user", "assistant")])


class BaseExtractor(ABC):
    """Contract that every AI-tool extractor must satisfy.

    This contract is retained for compatibility. New tools should implement
    ``agents.base.AgentAdapter`` so extraction and native sync are registered
    together.

    extract_all() must return a list of Session objects with source set to
    the tool's slug string (e.g. "opencode").
    """

    #: Human-readable name shown in the UI
    label: str

    #: Short slug used as Session.source and in API filters
    source: str

    @abstractmethod
    def extract_all(self) -> list[Session]:
        """Return all sessions found for this tool on the current machine."""
        ...

    def is_available(self) -> bool:
        """Return True if this tool's data directory exists on the machine."""
        return True
