# Contributing to AI Memory Vault

Thank you for your interest in contributing. This document covers everything you need to get started: project structure, how to add support for a new AI tool, running tests, and the pull request process.

---

## Quick start for contributors

```bash
git clone https://github.com/sbsepul/ai-memory-vault.git
cd ai-memory-vault

# Install in editable mode with dev dependencies
uv sync
# or: python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"

# Verify the CLI works
vault summary
```

---

## Project structure

```
src/ai_memory_vault/
├── extractors/          # reads raw data from each AI tool
│   ├── models.py        # Session and Message dataclasses — the shared data contract
│   ├── claude.py        # reads ~/.claude/projects/ JSONL files
│   ├── codex.py         # reads ~/.codex/sessions/ JSONL + session_index.jsonl
│   └── codex_memory.py  # reads ~/.codex/memories_1.sqlite
├── exporters/           # converts sessions to output formats
│   └── markdown.py      # writes Session objects to .md files
├── sync/                # git backup and restore logic
│   └── git.py           # vault push / vault pull implementation
├── resolver.py          # detects orphaned paths, maps old → new project locations
├── search.py            # full-text search across all sessions
├── status.py            # cross-references on-disk repos vs AI history
├── tree.py              # project-level aggregation and display
├── config.py            # all paths, defaults, and per-source metadata
├── utils.py             # shared helpers (path normalization, timestamp parsing)
└── cli.py               # Click command definitions — all vault subcommands
```

### The central data contract

Everything flows through `extractors/models.py`. An extractor reads raw files from an AI tool and returns a list of `Session` objects. Everything downstream (search, tree, export, sync) works with `Session` objects and never needs to know which tool produced them.

```python
# extractors/models.py
@dataclass
class Message:
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: datetime | None = None

@dataclass
class Session:
    id: str
    source: str               # "claude", "codex", or your new tool name
    project_rel_path: str     # relative to $HOME, e.g. "repos/my-project"
    name: str                 # human-readable session name
    started_at: datetime | None
    updated_at: datetime | None
    messages: list[Message]
    has_git: bool = False
```

The `project_rel_path` field is the most important one. It must be relative to `$HOME` so sessions are portable across machines with different usernames. Use `utils.rel_path_from_cwd(raw_cwd)` to convert an absolute path from the tool's data.

---

## How to add a new AI tool (e.g., Cursor)

This section walks through adding support for a fictional `cursor` tool that stores its sessions as JSON files in `~/.cursor/history/`. The same pattern applies to Windsurf, Zed, or any other tool.

### Step 1: Create the extractor module

Create `src/ai_memory_vault/extractors/cursor.py`. The only required public interface is `extract_all() -> list[Session]`.

```python
"""Extract sessions from Cursor (~/.cursor/history/)."""
from __future__ import annotations
import json
from pathlib import Path

from .models import Message, Session
from ..config import HOME
from ..utils import rel_path_from_cwd, parse_iso_timestamp

# Path to Cursor's session data — define this in config.py (see Step 2)
CURSOR_HISTORY_DIR = HOME / ".cursor" / "history"


def _parse_session_file(json_path: Path) -> Session | None:
    """Parse a single Cursor session file into a Session object."""
    try:
        data = json.loads(json_path.read_text(errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None

    # Extract the working directory and convert to a portable relative path.
    # rel_path_from_cwd strips the $HOME prefix, e.g.:
    #   /home/alice/repos/my-project  →  repos/my-project
    raw_cwd = data.get("workingDirectory", "")
    if not raw_cwd:
        return None
    project_rel_path = rel_path_from_cwd(raw_cwd)

    messages: list[Message] = []
    for turn in data.get("turns", []):
        ts = parse_iso_timestamp(turn.get("timestamp")) if turn.get("timestamp") else None

        user_text = turn.get("userMessage", "").strip()
        if user_text:
            messages.append(Message(role="user", content=user_text, timestamp=ts))

        assistant_text = turn.get("assistantMessage", "").strip()
        if assistant_text:
            messages.append(Message(role="assistant", content=assistant_text, timestamp=ts))

    if not messages:
        return None

    # Collect timestamps for started_at / updated_at
    all_ts = [m.timestamp for m in messages if m.timestamp]
    started_at = min(all_ts) if all_ts else None
    updated_at = max(all_ts) if all_ts else None

    return Session(
        id=json_path.stem,                        # use filename as session ID
        source="cursor",                           # must match the key in SOURCE_COLORS
        project_rel_path=project_rel_path,
        name=project_rel_path.split("/")[-1],     # last path component as display name
        started_at=started_at,
        updated_at=updated_at,
        messages=messages,
        has_git=(HOME / project_rel_path / ".git").exists(),
    )


def extract_all(history_dir: Path = CURSOR_HISTORY_DIR) -> list[Session]:
    """Return all Cursor sessions with relative project paths."""
    sessions: list[Session] = []
    if not history_dir.exists():
        return sessions
    for json_file in sorted(history_dir.rglob("*.json")):
        session = _parse_session_file(json_file)
        if session:
            sessions.append(session)
    return sessions
```

Study the existing extractors for reference:
- `extractors/claude.py` — decodes Claude's directory-name encoding, reads JSONL events
- `extractors/codex.py` — handles nested JSONL event envelopes, loads a separate thread-name index

### Step 2: Register the source in `config.py`

Open `src/ai_memory_vault/config.py` and add two things:

```python
# ── Tool data directories ─────────────────────────────────────────────────────
CLAUDE_PROJECTS_DIR = HOME / ".claude" / "projects"
CODEX_DIR           = HOME / ".codex"
CODEX_SESSIONS_DIR  = CODEX_DIR / "sessions"
CODEX_SESSION_INDEX = CODEX_DIR / "session_index.jsonl"
CURSOR_HISTORY_DIR  = HOME / ".cursor" / "history"   # ← add this

# ── Per-source display metadata ───────────────────────────────────────────────
# Extend this dict when adding a new source (Cursor, Windsurf, etc.)
SOURCE_COLORS: dict[str, str] = {
    "claude": "blue",
    "codex":  "green",
    "cursor": "yellow",   # ← add this; pick any Rich color name
}
```

`SOURCE_COLORS` controls how the source label is colored in CLI output. The key must exactly match the `source` field you set in `Session` objects.

### Step 3: Wire it into the session loader

The CLI collects sessions via a central loader. Find where `extractors.claude` and `extractors.codex` are imported and called — typically in `cli.py` or a shared helper — and add your extractor alongside them:

```python
from ai_memory_vault.extractors import claude, codex, cursor   # ← add cursor

def load_all_sessions(source: str | None = None) -> list[Session]:
    sessions: list[Session] = []
    if source in (None, "claude"):
        sessions.extend(claude.extract_all())
    if source in (None, "codex"):
        sessions.extend(codex.extract_all())
    if source in (None, "cursor"):
        sessions.extend(cursor.extract_all())          # ← add this
    return sessions
```

Also update any `--source` option that validates against a fixed list of tool names.

### Step 4: Verify

```bash
vault summary --source cursor
vault tree --source cursor
vault search "some keyword" --source cursor
```

If sessions show up with the correct project paths, you're done. If `project_rel_path` looks wrong, check what `raw_cwd` contains and whether `rel_path_from_cwd` handles it correctly.

---

## Running tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=ai_memory_vault

# Run a specific test file
uv run pytest tests/test_extractors.py
```

Tests for extractors live in `tests/`. When adding a new extractor, add a corresponding test file with at least:
- A test for `extract_all()` returning an empty list when the source directory does not exist
- A test parsing a representative fixture file and verifying `project_rel_path`, `source`, and `message_count`

---

## Code style

- Python 3.10+, type-annotated throughout
- `ruff` for linting and formatting: `uv run ruff check . && uv run ruff format .`
- No external dependencies beyond what is already in `pyproject.toml` — keep the install footprint small
- Prefer `pathlib.Path` over `os.path` everywhere
- Extractors must not write to disk or make network requests

---

## Pull request process

1. **Open an issue first** for any non-trivial change. This avoids duplicated effort and ensures the change aligns with the project direction.
2. Fork the repo and create a branch: `git checkout -b feat/cursor-support`
3. Make your changes, add tests, run `ruff` and `pytest`
4. Open a PR against `main` with a clear description of what changed and why
5. Link the issue in the PR description

---

## Reporting bugs

Open a GitHub issue with:
- Your OS and Python version
- Which AI tool's history triggered the bug (Claude Code, Codex, etc.)
- The output of `vault summary` (to confirm the tool is detected)
- The full error output (stack trace if available)

If the bug involves a specific session file, you can share a **sanitized** excerpt (replace real content with placeholder text).

---

## Feature requests and Roadmap discussion

The [Roadmap section of README.md](README.md#roadmap) lists what's planned. For anything on that list, an issue is the right place to coordinate. For new ideas not on the roadmap, open an issue to discuss before implementing — the scope of AI Memory Vault is intentionally focused on reading, preserving, and recalling session history, not on modifying it or integrating with AI tool internals.
