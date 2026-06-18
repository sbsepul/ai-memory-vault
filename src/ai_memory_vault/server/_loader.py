"""Shared session loader with 60-second in-memory cache."""

from __future__ import annotations

import time

from ..agents import AGENTS

_cache: dict = {"sessions": None, "loaded_at": 0.0}
_CACHE_TTL = 60


def get_all_sessions():
    now = time.monotonic()
    if _cache["sessions"] is None or (now - _cache["loaded_at"]) > _CACHE_TTL:
        sessions = []
        for adapter in AGENTS.select():
            sessions.extend(adapter.extract_sessions())
        _cache["sessions"] = sessions
        _cache["loaded_at"] = now

    return _cache["sessions"]


def invalidate():
    _cache["sessions"] = None
    _cache["loaded_at"] = 0.0
