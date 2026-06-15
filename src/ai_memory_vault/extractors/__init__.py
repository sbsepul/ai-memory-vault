"""Extractor registry.

To add a new AI tool:
  1. Create extractors/<tool>.py and subclass BaseExtractor
  2. Append an instance to EXTRACTORS here

The loader and CLI iterate EXTRACTORS — no other file needs to change.
"""
from .models import BaseExtractor, Message, Session
from .claude import ClaudeExtractor
from .codex import CodexExtractor

EXTRACTORS: list[BaseExtractor] = [
    ClaudeExtractor(),
    CodexExtractor(),
    # OpenCodeExtractor(),        # coming soon
    # CopilotCLIExtractor(),      # coming soon
]

__all__ = ["EXTRACTORS", "BaseExtractor", "Session", "Message"]
