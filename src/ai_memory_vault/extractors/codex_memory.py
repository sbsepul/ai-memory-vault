"""Backward-compatible Codex memory extractor import path."""

from ..domain.memories import CodexMemory
from ..infrastructure.extractors.codex_memory import extract_memories

__all__ = ["CodexMemory", "extract_memories"]
