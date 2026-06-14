"""Shared data models for extracted sessions."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass
class Message:
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: datetime | None = None


@dataclass
class Session:
    """Normalized session from either Claude or Codex."""
    id: str
    source: Literal["claude", "codex"]
    # Relative path from $HOME, e.g. "work/falabella-retail/platform/backend"
    project_rel_path: str
    # Human-readable name (thread_name for Codex, last dir component for Claude)
    name: str
    started_at: datetime | None
    updated_at: datetime | None
    messages: list[Message] = field(default_factory=list)
    # True if the project directory exists as a git repo
    has_git: bool = False
    # Original absolute path (for reference only, not used for portability)
    original_abs_path: str = ""

    @property
    def project_slug(self) -> str:
        """Last 2 path components as a kebab slug, e.g. 'backend-export-service'."""
        parts = [p for p in self.project_rel_path.split("/") if p]
        slug_parts = parts[-2:] if len(parts) >= 2 else parts
        return "-".join(slug_parts)

    @property
    def message_count(self) -> int:
        return len([m for m in self.messages if m.role in ("user", "assistant")])
