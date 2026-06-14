"""Memory-related domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class CodexMemory:
    thread_id: str
    project_rel_path: str
    thread_title: str
    raw_memory: str
    rollout_summary: str
    generated_at: datetime | None
    usage_count: int = 0
