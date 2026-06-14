"""Extract Codex memory summaries from SQLite."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ...config import CODEX_DIR
from ...domain.memories import CodexMemory
from ...utils import find_latest_sqlite, parse_iso_timestamp, rel_path_from_cwd


def _load_thread_metadata(state_db: Path) -> dict[str, tuple[str, str]]:
    meta: dict[str, tuple[str, str]] = {}
    if not state_db.exists():
        return meta
    try:
        connection = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
        cursor = connection.execute("SELECT id, cwd, title FROM threads")
        for thread_id, cwd, title in cursor.fetchall():
            meta[thread_id] = (cwd or "", title or "")
        connection.close()
    except sqlite3.Error:
        pass
    return meta


def extract_memories(codex_dir: Path = CODEX_DIR) -> list[CodexMemory]:
    memories_db = find_latest_sqlite(codex_dir, "memories")
    state_db = find_latest_sqlite(codex_dir, "state")

    if not memories_db or not memories_db.exists():
        return []

    thread_meta = _load_thread_metadata(state_db) if state_db else {}
    memories: list[CodexMemory] = []

    try:
        connection = sqlite3.connect(f"file:{memories_db}?mode=ro", uri=True)
        cursor = connection.execute(
            """
            SELECT thread_id, raw_memory, rollout_summary, generated_at, usage_count
            FROM stage1_outputs
            ORDER BY generated_at DESC
            """
        )
        for (
            thread_id,
            raw_memory,
            rollout_summary,
            generated_at_str,
            usage_count,
        ) in cursor.fetchall():
            cwd, title = thread_meta.get(thread_id, ("", ""))
            rel_path = rel_path_from_cwd(cwd) if cwd else "(unknown)"
            generated_at = parse_iso_timestamp(str(generated_at_str)) if generated_at_str else None
            memories.append(
                CodexMemory(
                    thread_id=thread_id,
                    project_rel_path=rel_path,
                    thread_title=title,
                    raw_memory=raw_memory or "",
                    rollout_summary=rollout_summary or "",
                    generated_at=generated_at,
                    usage_count=usage_count or 0,
                )
            )
        connection.close()
    except sqlite3.Error:
        pass

    return memories
