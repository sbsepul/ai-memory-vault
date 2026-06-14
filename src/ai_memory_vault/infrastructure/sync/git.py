"""Push and pull sessions to/from a private git vault repository."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ...config import (
    CLAUDE_PROJECTS_DIR,
    CONFIG_DIR,
    CONFIG_FILE,
    HOME,
    VAULT_EXPORTS_SUBDIR,
    VAULT_LOCAL,
    VAULT_RAW_CLAUDE_SUBDIR,
)


def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


def _run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def _resolve_vault_repo(vault_repo: str | None) -> str:
    config = load_config()
    if vault_repo:
        config["vault_repo"] = vault_repo
        save_config(config)
        return vault_repo
    if "vault_repo" in config:
        return config["vault_repo"]
    raise ValueError("No vault repo configured. Pass --vault-repo <url> on first use.")


def _default_branch(vault_local: Path) -> str:
    code, out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=vault_local)
    branch = out.strip()
    return branch if code == 0 and branch and branch != "HEAD" else "main"


def _ensure_vault_local(vault_repo: str) -> Path:
    VAULT_LOCAL.parent.mkdir(parents=True, exist_ok=True)

    if not (VAULT_LOCAL / ".git").exists():
        code, _ = _run(["git", "clone", vault_repo, str(VAULT_LOCAL)], cwd=HOME)
        if code != 0:
            VAULT_LOCAL.mkdir(parents=True, exist_ok=True)
            _run(["git", "init", "-b", "main"], cwd=VAULT_LOCAL)
            _run(["git", "remote", "add", "origin", vault_repo], cwd=VAULT_LOCAL)
    else:
        branch = _default_branch(VAULT_LOCAL)
        _run(["git", "pull", "--rebase", "origin", branch], cwd=VAULT_LOCAL)

    return VAULT_LOCAL


def _decode_claude_slug(slug: str) -> str:
    abs_path = slug.replace("-", "/").lstrip("/")
    home_str = str(HOME).lstrip("/")
    if abs_path.startswith(home_str):
        return abs_path[len(home_str) :].lstrip("/") or "home"
    return abs_path


def _encode_claude_slug(rel_path: str) -> str:
    return str(HOME / rel_path).replace("/", "-")


def backup_raw_claude(vault_local: Path) -> int:
    if not CLAUDE_PROJECTS_DIR.exists():
        return 0

    raw_dest = vault_local / VAULT_RAW_CLAUDE_SUBDIR
    count = 0
    for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        rel_path = _decode_claude_slug(project_dir.name)
        dest_project = raw_dest / rel_path
        dest_project.mkdir(parents=True, exist_ok=True)

        for jsonl_file in project_dir.glob("*.jsonl"):
            shutil.copy2(str(jsonl_file), str(dest_project / jsonl_file.name))
            count += 1

    return count


def restore_raw_claude(vault_local: Path, dry_run: bool = False) -> list[tuple[str, str]]:
    raw_src = vault_local / VAULT_RAW_CLAUDE_SUBDIR
    if not raw_src.exists():
        return []

    restored: list[tuple[str, str]] = []
    for jsonl_file in raw_src.rglob("*.jsonl"):
        rel_path = str(jsonl_file.parent.relative_to(raw_src))
        new_slug = _encode_claude_slug(rel_path)
        dest_dir = CLAUDE_PROJECTS_DIR / new_slug
        dest_file = dest_dir / jsonl_file.name

        if dry_run:
            restored.append((rel_path, new_slug))
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)
        if not dest_file.exists():
            shutil.copy2(str(jsonl_file), str(dest_file))
            restored.append((rel_path, new_slug))

    return restored


def push_to_vault(
    export_dir: Path,
    vault_repo: str | None,
    *,
    include_raw: bool = False,
    message: str | None = None,
) -> str:
    resolved_repo = _resolve_vault_repo(vault_repo)
    vault_local = _ensure_vault_local(resolved_repo)

    if export_dir.exists():
        shutil.copytree(
            str(export_dir),
            str(vault_local / VAULT_EXPORTS_SUBDIR),
            dirs_exist_ok=True,
        )

    raw_count = backup_raw_claude(vault_local) if include_raw else 0
    _run(["git", "add", "-A"], cwd=vault_local)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    suffix = f" (+{raw_count} raw files)" if raw_count else ""
    commit_message = message or f"vault: export snapshot {timestamp}{suffix}"

    code, out = _run(["git", "commit", "-m", commit_message], cwd=vault_local)
    if code != 0 and "nothing to commit" in out:
        return "nothing to commit"

    branch = _default_branch(vault_local)
    push_code, _ = _run(["git", "push", "-u", "origin", branch], cwd=vault_local)
    if push_code != 0:
        _run(
            ["git", "push", "-u", "origin", f"HEAD:{branch}", "--force-with-lease"],
            cwd=vault_local,
        )

    return commit_message


class PullResult:
    def __init__(self) -> None:
        self.export_files: int = 0
        self.restored_sessions: list[tuple[str, str]] = []
        self.vault_local: Path = VAULT_LOCAL
        self.already_up_to_date: bool = False


def pull_from_vault(
    vault_repo: str | None,
    output_dir: Path,
    *,
    restore_claude: bool = False,
    dry_run: bool = False,
) -> PullResult:
    resolved_repo = _resolve_vault_repo(vault_repo)
    result = PullResult()

    vault_local = _ensure_vault_local(resolved_repo)
    result.vault_local = vault_local

    _, pull_out = _run(["git", "log", "--oneline", "-1"], cwd=vault_local)
    result.already_up_to_date = "Already up to date" in pull_out

    exports_src = vault_local / VAULT_EXPORTS_SUBDIR
    if exports_src.exists() and not dry_run:
        shutil.copytree(str(exports_src), str(output_dir), dirs_exist_ok=True)
        result.export_files = sum(1 for _ in output_dir.rglob("*.md"))

    if restore_claude:
        result.restored_sessions = restore_raw_claude(vault_local, dry_run=dry_run)

    return result
