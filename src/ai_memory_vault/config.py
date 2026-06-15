"""Central configuration: paths, defaults, and per-source metadata.

All paths are derived from Path.home() so they work on any machine
regardless of username or OS. Add new sources here to make them
visible to the rest of the codebase without touching individual modules.
"""
from __future__ import annotations
from pathlib import Path

HOME = Path.home()

# ── Tool data directories ─────────────────────────────────────────────────────
CLAUDE_PROJECTS_DIR = HOME / ".claude" / "projects"

CODEX_DIR           = HOME / ".codex"
CODEX_SESSIONS_DIR  = CODEX_DIR / "sessions"
CODEX_SESSION_INDEX = CODEX_DIR / "session_index.jsonl"

# ── vault config & local cache ────────────────────────────────────────────────
CONFIG_DIR    = HOME / ".config" / "ai-memory-vault"
CONFIG_FILE   = CONFIG_DIR / "config.json"
PATH_MAP_FILE      = CONFIG_DIR / "path-map.json"
SKIP_NAMES_FILE    = CONFIG_DIR / "skip-names.json"
VAULT_LOCAL   = HOME / ".local" / "share" / "ai-memory-vault" / "vault"

# ── vault repo layout ─────────────────────────────────────────────────────────
VAULT_EXPORTS_SUBDIR    = "exports"
VAULT_RAW_CLAUDE_SUBDIR = "raw/claude"

# ── CLI defaults ──────────────────────────────────────────────────────────────
DEFAULT_OUTPUT_DIR    = HOME / "ai-memory-vault-export"
DEFAULT_SEARCH_DIRS   = [HOME / "repos", HOME / "work"]
DEFAULT_SEARCH_DEPTH  = 5
DEFAULT_LS_LIMIT      = 50
DEFAULT_SEARCH_LIMIT  = 20
DEFAULT_MEMORIES_LIMIT = 50
SNIPPET_CONTEXT_CHARS = 80

# ── Per-source display metadata ───────────────────────────────────────────────
# Extend this dict when adding a new source (Cursor, Windsurf, etc.)
SOURCE_COLORS: dict[str, str] = {
    "claude": "blue",
    "codex":  "green",
}

# ── Algorithm tuning ──────────────────────────────────────────────────────────
GIT_REMOTE_TIMEOUT_S    = 3
RESOLVER_MIN_NAME_LEN   = 5
RESOLVER_SIMILARITY_GAP = 0.15
