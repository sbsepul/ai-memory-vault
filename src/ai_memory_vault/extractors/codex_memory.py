"""
Extract Codex auto-generated memory summaries from ~/.codex/memories_1.sqlite.

Codex silently builds condensed memories per thread after each session.
These are stored in SQLite, not in the JSONL session files, so the main
codex.py extractor never sees them. This module surfaces them separately.

SQLite files used and ignored:
  memories_1.sqlite  — thread memory summaries          ← READ (this module)
  state_5.sqlite     — thread metadata index            ← READ (thread titles/cwd)
  logs_2.sqlite      — app debug logs (243 MB)          ← IGNORED (no conv. data)
  goals_1.sqlite     — goals tracking (empty)           ← IGNORED
"""
from __future__ import annotations
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_HOME = Path.home()
_CODEX_DIR = _HOME / ".codex"
_MEMORIES_DB = _CODEX_DIR / "memories_1.sqlite"
_STATE_DB = _CODEX_DIR / "state_5.sqlite"


@dataclass
class CodexMemory:
    thread_id: str
    project_rel_path: str     # relative to $HOME, e.g. "work/my-company/backend"
    thread_title: str
    raw_memory: str           # full text of the memory Codex generated
    rollout_summary: str      # shorter rollout-level summary
    generated_at: datetime | None
    usage_count: int = 0


def _rel_path(cwd: str) -> str:
    home_str = str(_HOME)
    if cwd.startswith(home_str):
        return cwd[len(home_str):].lstrip("/") or "home"
    return cwd.lstrip("/")


def _load_thread_metadata() -> dict[str, tuple[str, str]]:
    """Return {thread_id: (cwd, title)} from state_5.sqlite."""
    meta: dict[str, tuple[str, str]] = {}
    if not _STATE_DB.exists():
        return meta
    try:
        con = sqlite3.connect(f"file:{_STATE_DB}?mode=ro", uri=True)
        cur = con.execute("SELECT id, cwd, title FROM threads")
        for row in cur.fetchall():
            tid, cwd, title = row
            meta[tid] = (cwd or "", title or "")
        con.close()
    except sqlite3.Error:
        pass
    return meta


def extract_memories(memories_db: Path = _MEMORIES_DB) -> list[CodexMemory]:
    """Return all Codex auto-generated memory summaries."""
    if not memories_db.exists():
        return []

    thread_meta = _load_thread_metadata()
    memories: list[CodexMemory] = []

    try:
        con = sqlite3.connect(f"file:{memories_db}?mode=ro", uri=True)
        cur = con.execute(
            """
            SELECT thread_id, raw_memory, rollout_summary,
                   generated_at, usage_count
            FROM stage1_outputs
            ORDER BY generated_at DESC
            """
        )
        for row in cur.fetchall():
            tid, raw_memory, rollout_summary, generated_at_str, usage_count = row
            cwd, title = thread_meta.get(tid, ("", ""))
            rel_path = _rel_path(cwd) if cwd else "(unknown)"

            generated_at: datetime | None = None
            if generated_at_str:
                try:
                    generated_at = datetime.fromisoformat(
                        str(generated_at_str).replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            memories.append(CodexMemory(
                thread_id=tid,
                project_rel_path=rel_path,
                thread_title=title,
                raw_memory=raw_memory or "",
                rollout_summary=rollout_summary or "",
                generated_at=generated_at,
                usage_count=usage_count or 0,
            ))
        con.close()
    except sqlite3.Error:
        pass

    return memories
