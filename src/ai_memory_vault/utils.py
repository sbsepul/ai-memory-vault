"""Shared utility functions used across extractors and commands."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import HOME


def rel_path_from_cwd(cwd: str) -> str:
    """Convert an absolute cwd to a portable path relative to $HOME.

    Paths outside $HOME are returned as-is (minus a leading slash) so
    sessions from unusual locations are still represented portably.
    """
    home_str = str(HOME)
    if cwd.startswith(home_str):
        return cwd[len(home_str) :].lstrip("/") or "home"
    return cwd.lstrip("/")


def parse_iso_timestamp(ts_raw: str) -> datetime | None:
    """Parse an ISO 8601 string, including the 'Z' suffix variant. Returns None on failure."""
    try:
        return datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def fmt_ts(ts: datetime | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Format a datetime for display; returns '?' when ts is None."""
    return ts.strftime(fmt) if ts else "?"


def find_latest_sqlite(directory: Path, prefix: str) -> Path | None:
    """Return the highest-versioned file matching {prefix}_*.sqlite, or None.

    Codex names its databases with a version suffix that may bump on upgrades
    (e.g. memories_1.sqlite → memories_2.sqlite). Scanning for the latest
    version avoids breakage when Codex ships a schema migration.
    """
    candidates = sorted(directory.glob(f"{prefix}_*.sqlite"))
    return candidates[-1] if candidates else None
