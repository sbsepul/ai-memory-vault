"""
Intelligently match orphan AI history paths to their current canonical
repo location on disk.

Two signals, in order of confidence:
  1. Git remote URL — strongest: same remote = same project, regardless of
     where it's cloned.
  2. Normalized name — strip hyphens/underscores/dots and compare the last
     path component (e.g. 'dream_home', 'dream-home', 'Dream Home' all
     become 'dreamhome').  When a single disk repo matches, it's likely
     the same project.  When multiple match, the one with the most
     similar parent path wins.

The resolved mapping is persisted to
~/.config/ai-memory-vault/path-map.json so it survives between runs and
can be hand-edited if needed.
"""
from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path

from .config import (
    HOME, PATH_MAP_FILE, CONFIG_DIR,
    GIT_REMOTE_TIMEOUT_S, RESOLVER_MIN_NAME_LEN, RESOLVER_SIMILARITY_GAP,
)


# Names too generic to match confidently
_SKIP_NAMES = {"home", "repos", "work", "src", "app", "api", "web", "data",
               "backend", "frontend", "claude", "downloads", "skills",
               "personal", "universal", "platform", "services", "packages"}


# ── helpers ───────────────────────────────────────────────────────────────────

def _normalize_name(name: str) -> str:
    """'dream-home', 'dream_home', 'Dream Home' → 'dreamhome'"""
    return re.sub(r"[-_.\s]", "", name).lower()


def _normalize_remote(url: str) -> str:
    """Strip protocol/host/user and .git suffix → bare repo name."""
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
    """Fraction of path components shared from right to left."""
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
    """Return {normalized_remote: rel_path} for all disk repos that have a remote."""
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
) -> dict[str, str]:
    """
    Return {orphan_path: canonical_disk_path} for every orphan that can be
    matched confidently to a current repo on disk.

    Conservative rules — we prefer false negatives over false positives:
      1. Git remote URL of a named candidate matches the orphan name exactly.
      2. Exactly one disk repo has the same normalized last component AND
         the normalized name is specific enough (len ≥ RESOLVER_MIN_NAME_LEN).
      3. Multiple candidates → pick the one with the highest parent-path
         similarity, but only if the gap over second place is significant
         (≥ RESOLVER_SIMILARITY_GAP).
    """
    remote_index = _build_remote_index(disk_repos)

    name_index: dict[str, list[str]] = {}
    for rel in disk_repos:
        key = _normalize_name(rel.split("/")[-1])
        name_index.setdefault(key, []).append(rel)

    mapping: dict[str, str] = {}

    for orphan in orphan_paths:
        orphan_name = orphan.split("/")[-1]
        norm = _normalize_name(orphan_name)

        if norm in _SKIP_NAMES or len(norm) < RESOLVER_MIN_NAME_LEN:
            continue

        # Signal 1: git remote exact match
        matched_via_remote: str | None = None
        for remote_key, disk_path in remote_index.items():
            if norm == _normalize_name(remote_key.split("/")[-1]):
                matched_via_remote = disk_path
                break
        if matched_via_remote:
            mapping[orphan] = matched_via_remote
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
            top_score = scored[0][1]
            second_score = scored[1][1] if len(scored) > 1 else 0
            if top_score > 0 and (top_score - second_score) >= RESOLVER_SIMILARITY_GAP:
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
    """Resolve an orphan path to its canonical location, or return as-is."""
    return path_map.get(rel_path, rel_path)
