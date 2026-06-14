"""Push and pull sessions to/from a private git vault repository."""
from __future__ import annotations
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

_HOME = Path.home()
_CONFIG_DIR = _HOME / ".config" / "ai-memory-vault"
_CONFIG_FILE = _CONFIG_DIR / "config.json"
_VAULT_LOCAL = _HOME / ".local" / "share" / "ai-memory-vault" / "vault"

# Where raw Claude JSONL files are stored inside the vault repo
_RAW_CLAUDE_SUBDIR = "raw/claude"


def load_config() -> dict:
    if _CONFIG_FILE.exists():
        return json.loads(_CONFIG_FILE.read_text())
    return {}


def save_config(data: dict) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(data, indent=2))


def _run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def _resolve_vault_repo(vault_repo: str | None) -> str:
    cfg = load_config()
    if vault_repo:
        cfg["vault_repo"] = vault_repo
        save_config(cfg)
        return vault_repo
    if "vault_repo" in cfg:
        return cfg["vault_repo"]
    raise ValueError(
        "No vault repo configured. Pass --vault-repo <url> on first use."
    )


def _ensure_vault_local(vault_repo: str) -> Path:
    """Clone or update the local copy of the vault repo. Returns its path."""
    _VAULT_LOCAL.parent.mkdir(parents=True, exist_ok=True)

    if not (_VAULT_LOCAL / ".git").exists():
        code, out = _run(["git", "clone", vault_repo, str(_VAULT_LOCAL)], cwd=_HOME)
        if code != 0:
            # Empty or brand-new repo: init locally and set remote
            _VAULT_LOCAL.mkdir(parents=True, exist_ok=True)
            _run(["git", "init", "-b", "main"], cwd=_VAULT_LOCAL)
            _run(["git", "remote", "add", "origin", vault_repo], cwd=_VAULT_LOCAL)
    else:
        _run(["git", "pull", "--rebase", "origin", "main"], cwd=_VAULT_LOCAL)

    return _VAULT_LOCAL


def _decode_claude_slug(slug: str) -> str:
    """
    Convert a Claude project directory slug back to a relative path from $HOME.
    e.g. '-home-sbsepul-repos-dream-home' -> 'repos/dream-home'
    """
    abs_path = slug.replace("-", "/").lstrip("/")
    home_str = str(_HOME).lstrip("/")
    if abs_path.startswith(home_str):
        return abs_path[len(home_str):].lstrip("/") or "home"
    return abs_path


def _encode_claude_slug(rel_path: str) -> str:
    """
    Convert a relative path to the Claude project directory slug for the current machine.
    'repos/dream-home' -> '-home-newuser-repos-dream-home'
    """
    abs_path = str(_HOME / rel_path)   # /home/newuser/repos/dream-home
    return abs_path.replace("/", "-")  # -home-newuser-repos-dream-home


def backup_raw_claude(vault_local: Path) -> int:
    """
    Copy raw Claude JSONL files into the vault using relative paths.
    Returns the number of session files copied.
    """
    claude_projects = _HOME / ".claude" / "projects"
    if not claude_projects.exists():
        return 0

    raw_dest = vault_local / _RAW_CLAUDE_SUBDIR
    count = 0

    for project_dir in claude_projects.iterdir():
        if not project_dir.is_dir():
            continue
        rel_path = _decode_claude_slug(project_dir.name)
        dest_project = raw_dest / rel_path
        dest_project.mkdir(parents=True, exist_ok=True)

        for jsonl_file in project_dir.glob("*.jsonl"):
            dest_file = dest_project / jsonl_file.name
            shutil.copy2(str(jsonl_file), str(dest_file))
            count += 1

    return count


def restore_raw_claude(vault_local: Path, dry_run: bool = False) -> list[tuple[str, str]]:
    """
    Restore raw Claude JSONL files from the vault to ~/.claude/projects/,
    re-encoding the project directory slug for the current machine's $HOME.

    Returns a list of (source_rel_path, dest_slug) pairs for reporting.
    """
    raw_src = vault_local / _RAW_CLAUDE_SUBDIR
    if not raw_src.exists():
        return []

    claude_projects = _HOME / ".claude" / "projects"
    restored: list[tuple[str, str]] = []

    # raw_src structure: raw/claude/{rel_path}/{session}.jsonl
    # We need to walk two levels deep to find project dirs
    for jsonl_file in raw_src.rglob("*.jsonl"):
        # rel_path is everything between raw/claude/ and the filename
        rel_path = str(jsonl_file.parent.relative_to(raw_src))
        new_slug = _encode_claude_slug(rel_path)
        dest_dir = claude_projects / new_slug
        dest_file = dest_dir / jsonl_file.name

        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
            if not dest_file.exists():
                shutil.copy2(str(jsonl_file), str(dest_file))
                restored.append((rel_path, new_slug))
        else:
            restored.append((rel_path, new_slug))

    return restored


# ── push ─────────────────────────────────────────────────────────────────────

def push_to_vault(
    export_dir: Path,
    vault_repo: str | None,
    *,
    include_raw: bool = False,
    message: str | None = None,
) -> str:
    """
    Export Markdown sessions (and optionally raw Claude JSONL) to the vault repo.
    Returns the commit message, or 'nothing to commit'.
    """
    vault_repo = _resolve_vault_repo(vault_repo)
    vault_local = _ensure_vault_local(vault_repo)

    # Copy Markdown/JSON exports
    if export_dir.exists():
        shutil.copytree(str(export_dir), str(vault_local / "exports"), dirs_exist_ok=True)

    raw_count = 0
    if include_raw:
        raw_count = backup_raw_claude(vault_local)

    _run(["git", "add", "-A"], cwd=vault_local)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    suffix = f" (+{raw_count} raw files)" if raw_count else ""
    commit_msg = message or f"vault: export snapshot {ts}{suffix}"

    code, out = _run(["git", "commit", "-m", commit_msg], cwd=vault_local)
    if code != 0 and "nothing to commit" in out:
        return "nothing to commit"

    push_code, _ = _run(["git", "push", "-u", "origin", "main"], cwd=vault_local)
    if push_code != 0:
        _run(["git", "push", "-u", "origin", "HEAD:main", "--force-with-lease"], cwd=vault_local)

    return commit_msg


# ── pull ─────────────────────────────────────────────────────────────────────

class PullResult:
    def __init__(self):
        self.export_files: int = 0
        self.restored_sessions: list[tuple[str, str]] = []
        self.vault_local: Path = _VAULT_LOCAL
        self.already_up_to_date: bool = False


def pull_from_vault(
    vault_repo: str | None,
    output_dir: Path,
    *,
    restore_claude: bool = False,
    dry_run: bool = False,
) -> PullResult:
    """
    Pull exports from the vault repo to output_dir.
    If restore_claude=True, also restore raw JSONL files to ~/.claude/projects/
    with the current machine's $HOME re-encoded into the directory slug.
    """
    vault_repo = _resolve_vault_repo(vault_repo)
    result = PullResult()

    code, out = _run(["git", "status", "--porcelain"], cwd=_VAULT_LOCAL) \
        if (_VAULT_LOCAL / ".git").exists() else (1, "")

    vault_local = _ensure_vault_local(vault_repo)
    result.vault_local = vault_local

    # Check if pull brought anything new
    _, pull_out = _run(["git", "log", "--oneline", "-1"], cwd=vault_local)
    result.already_up_to_date = "Already up to date" in pull_out

    # Copy exports to output_dir
    exports_src = vault_local / "exports"
    if exports_src.exists() and not dry_run:
        shutil.copytree(str(exports_src), str(output_dir), dirs_exist_ok=True)
        result.export_files = sum(1 for _ in output_dir.rglob("*.md"))

    if restore_claude:
        result.restored_sessions = restore_raw_claude(vault_local, dry_run=dry_run)

    return result
