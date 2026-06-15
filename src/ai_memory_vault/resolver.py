"""
Intelligently match orphan AI history paths to their current canonical
repo location on disk.

Two signals, in order of confidence:
  1. Git remote URL — strongest: same remote = same project, regardless of
     where it's cloned.
  2. Normalized name — strip hyphens/underscores/dots and compare the last
     path component.  When a single disk repo matches, it's likely the same
     project.  When multiple match, the one with the most similar parent
     path wins.

Generic (container) directory names are excluded from matching automatically.
They are derived from the user's own session data — any path segment that
appears as an intermediate (non-leaf) directory in 2+ session paths is
considered too generic to match on.  The derived set is persisted to
~/.config/ai-memory-vault/skip-names.json so it survives between runs and
can be hand-edited if needed.
"""
from __future__ import annotations
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from .config import (
    HOME, PATH_MAP_FILE, SKIP_NAMES_FILE, CONFIG_DIR,
    GIT_REMOTE_TIMEOUT_S, RESOLVER_MIN_NAME_LEN, RESOLVER_SIMILARITY_GAP,
)


# ── skip-names: auto-derived, persisted ───────────────────────────────────────

def build_skip_names(session_paths: list[str], min_count: int = 10) -> set[str]:
    """Derive generic container-dir names from the user's actual session paths.

    Any segment that appears as a non-leaf (intermediate directory) in
    `min_count` or more distinct paths is considered a container, not a
    project name, and is added to the skip set.
    """
    counts: Counter[str] = Counter()
    for path in session_paths:
        parts = path.strip("/").split("/")
        for seg in parts[:-1]:   # every component except the leaf
            if seg:
                counts[seg] += 1
    return {name for name, count in counts.items() if count >= min_count}


def load_skip_names() -> set[str]:
    """Load persisted skip-names from config, or return empty set."""
    if SKIP_NAMES_FILE.exists():
        try:
            return set(json.loads(SKIP_NAMES_FILE.read_text()))
        except (json.JSONDecodeError, TypeError):
            pass
    return set()


def save_skip_names(names: set[str]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SKIP_NAMES_FILE.write_text(
        json.dumps(sorted(names), indent=2, ensure_ascii=False)
    )


def refresh_skip_names(session_paths: list[str], min_count: int = 10) -> set[str]:
    """Re-derive skip names from current session data and persist them."""
    names = build_skip_names(session_paths, min_count)
    save_skip_names(names)
    return names


def get_skip_names(session_paths: list[str] | None = None) -> set[str]:
    """Return skip names: load from file if it exists, otherwise derive and save."""
    if SKIP_NAMES_FILE.exists():
        return load_skip_names()
    if session_paths is not None:
        return refresh_skip_names(session_paths)
    return set()


# ── helpers ───────────────────────────────────────────────────────────────────

def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.\s]", "", name).lower()


def _normalize_remote(url: str) -> str:
    url = re.sub(r"\.git$", "", url.strip())
    parts = re.split(r"[:/]", url)
    return "/".join(parts[-2:]).lower() if len(parts) >= 2 else url.lower()


def _git_remote(repo_path: Path) -> str | None:
    try:
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True,
            cwd=repo_path, timeout=GIT_REMOTE_TIMEOUT_S,
        )
        return r.stdout.strip() or None
    except Exception:
        return None


def _path_similarity(a: str, b: str) -> float:
    pa = a.strip("/").split("/")
    pb = b.strip("/").split("/")
    shared = 0
    for x, y in zip(reversed(pa), reversed(pb)):
        if _normalize_name(x) == _normalize_name(y):
            shared += 1
        else:
            break
    return shared / max(len(pa), len(pb))


# ── remote index ──────────────────────────────────────────────────────────────

def _build_remote_index(disk_repos: set[str]) -> dict[str, str]:
    index: dict[str, str] = {}
    for rel in disk_repos:
        remote = _git_remote(HOME / rel)
        if remote:
            index[_normalize_remote(remote)] = rel
    return index


# ── main resolver ─────────────────────────────────────────────────────────────

def resolve_orphans(
    orphan_paths: set[str],
    disk_repos: set[str],
    skip_names: set[str] | None = None,
) -> dict[str, str]:
    """
    Return {orphan_path: canonical_disk_path} for every orphan that can be
    matched confidently to a current repo on disk.

    `skip_names` defaults to the persisted set from ~/.config/ai-memory-vault/
    skip-names.json.  Pass an explicit set (e.g. from refresh_skip_names) to
    override.
    """
    if skip_names is None:
        all_paths = list(orphan_paths) + list(disk_repos)
        skip_names = get_skip_names(all_paths)

    remote_index = _build_remote_index(disk_repos)

    name_index: dict[str, list[str]] = {}
    for rel in disk_repos:
        key = _normalize_name(rel.split("/")[-1])
        name_index.setdefault(key, []).append(rel)

    mapping: dict[str, str] = {}

    for orphan in orphan_paths:
        orphan_name = orphan.split("/")[-1]
        norm = _normalize_name(orphan_name)

        if norm in {_normalize_name(s) for s in skip_names}:
            continue
        if len(norm) < RESOLVER_MIN_NAME_LEN:
            continue

        # Signal 1: git remote exact match
        for remote_key, disk_path in remote_index.items():
            if norm == _normalize_name(remote_key.split("/")[-1]):
                mapping[orphan] = disk_path
                break
        if orphan in mapping:
            continue

        # Signal 2: unique normalized name match
        candidates = name_index.get(norm, [])

        if len(candidates) == 1:
            mapping[orphan] = candidates[0]
            continue

        if len(candidates) > 1:
            # Signal 3: parent path similarity with clear winner
            scored = sorted(
                [(c, _path_similarity(orphan, c)) for c in candidates],
                key=lambda x: -x[1],
            )
            top, second = scored[0][1], (scored[1][1] if len(scored) > 1 else 0)
            if top > 0 and (top - second) >= RESOLVER_SIMILARITY_GAP:
                mapping[orphan] = scored[0][0]

    return mapping


# ── persistence ───────────────────────────────────────────────────────────────

def load_path_map() -> dict[str, str]:
    if PATH_MAP_FILE.exists():
        return json.loads(PATH_MAP_FILE.read_text())
    return {}


def save_path_map(mapping: dict[str, str]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PATH_MAP_FILE.write_text(json.dumps(mapping, indent=2, ensure_ascii=False))


def apply_path_map(rel_path: str, path_map: dict[str, str]) -> str:
    return path_map.get(rel_path, rel_path)
