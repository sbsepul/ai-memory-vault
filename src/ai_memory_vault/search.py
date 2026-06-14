"""Full-text search across extracted sessions."""
from __future__ import annotations
import re
from dataclasses import dataclass

from .extractors.models import Session, Message


@dataclass
class SearchHit:
    session: Session
    message: Message
    snippet: str          # excerpt with match highlighted
    match_index: int      # position of match in message content


def search(
    sessions: list[Session],
    query: str,
    *,
    case_sensitive: bool = False,
) -> list[SearchHit]:
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(re.escape(query), flags)
    except re.error:
        pattern = re.compile(query, flags)

    hits: list[SearchHit] = []
    for session in sessions:
        for msg in session.messages:
            if msg.role not in ("user", "assistant"):
                continue
            m = pattern.search(msg.content)
            if not m:
                continue
            start = max(0, m.start() - 80)
            end = min(len(msg.content), m.end() + 80)
            snippet = msg.content[start:end].replace("\n", " ")
            if start > 0:
                snippet = "…" + snippet
            if end < len(msg.content):
                snippet = snippet + "…"
            hits.append(SearchHit(
                session=session,
                message=msg,
                snippet=snippet,
                match_index=m.start(),
            ))

    return hits
