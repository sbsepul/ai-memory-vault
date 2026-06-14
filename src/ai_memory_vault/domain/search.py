"""Search result domain models."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Message, Session


@dataclass
class SearchHit:
    session: Session
    message: Message
    snippet: str
    match_index: int
