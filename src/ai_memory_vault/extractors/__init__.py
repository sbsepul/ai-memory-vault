"""Legacy extractor classes.

New integrations must implement ``agents.base.AgentAdapter`` and register in
``agents.registry.AGENTS``. ``EXTRACTORS`` remains only for import compatibility.
"""

from .claude import ClaudeExtractor
from .codex import CodexExtractor
from .models import BaseExtractor, Message, Session

EXTRACTORS: list[BaseExtractor] = [
    ClaudeExtractor(),
    CodexExtractor(),
    # OpenCodeExtractor(),        # coming soon
    # CopilotCLIExtractor(),      # coming soon
]

__all__ = ["EXTRACTORS", "BaseExtractor", "Session", "Message"]
