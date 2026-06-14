"""
Extract Codex auto-generated memory summaries from ~/.codex/memories_N.sqlite.

Codex silently builds condensed memories per thread after each session.
These are stored in SQLite, not in the JSONL session files, so the main
codex.py extractor never sees them. This module surfaces them separately.

SQLite files used and ignored:
  memories_N.sqlite  — thread memory summaries          ← READ (this module)
  state_N.sqlite     — thread metadata index            ← READ (thread titles/cwd)
  logs_N.sqlite      — app debug logs (~243 MB)         ← IGNORED (no conv. data)
  goals_N.sqlite     — goals tracking (empty)           ← IGNORED

The version suffix (N) is determined at runtime by scanning for the
highest-numbered file, so upgrades to newer Codex schema versions are
handled automatically.
"""
from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..config import CODEX_DIR
from ..utils import rel_path_from_cwd, parse_iso_timestamp, find_latest_sqlite


@dataclass
class CodexMemory:
    thread_id: str
    project_rel_path: str     # relative to $HOME, e.g. "work/my-company/backend"
    thread_title: str
    raw_memory: str           # full text of the memory Codex generated
    rollout_summary: str      # shorter rollout-level summary
    generated_at: datetime | None
    usage_count: int = 0


def _load_thread_metadata(state_db: Path) -> dict[str, tuple[str, str]]:
    """Return {thread_id: (cwd, title)} from the state SQLite database."""
    meta: dict[str, tuple[str, str]] = {}
    if not state_db.exists():
        return meta
    try:
        con = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
        cur = con.execute("SELECT id, cwd, title FROM threads")
        for tid, cwd, title in cur.fetchall():
            meta[tid] = (cwd or "", title or "")
        con.close()
    except sqlite3.Error:
        pass
    return meta


def extract_memories(codex_dir: Path = CODEX_DIR) -> list[CodexMemory]:
    """Return all Codex auto-generated memory summaries.

    Scans for the latest memories_N.sqlite and state_N.sqlite so the
    function keeps working when Codex bumps its schema version number.
    """
    memories_db = find_latest_sqlite(codex_dir, "memories")
    state_db    = find_latest_sqlite(codex_dir, "state")

    if not memories_db or not memories_db.exists():
        return []

    thread_meta = _load_thread_metadata(state_db) if state_db else {}
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
        for tid, raw_memory, rollout_summary, generated_at_str, usage_count in cur.fetchall():
            cwd, title = thread_meta.get(tid, ("", ""))
            rel_path = rel_path_from_cwd(cwd) if cwd else "(unknown)"
            generated_at = parse_iso_timestamp(str(generated_at_str)) if generated_at_str else None

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
