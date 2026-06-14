"""Push exported sessions to a private git repository."""
from __future__ import annotations
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "ai-memory-vault"
_CONFIG_FILE = _CONFIG_DIR / "config.json"


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


def push_to_vault(
    export_dir: Path,
    vault_repo: str | None,
    *,
    message: str | None = None,
) -> str:
    """
    Clone or update a private vault repo, copy exports into it, commit and push.
    Returns the commit message used.
    """
    cfg = load_config()

    if vault_repo:
        cfg["vault_repo"] = vault_repo
        save_config(cfg)
    elif "vault_repo" in cfg:
        vault_repo = cfg["vault_repo"]
    else:
        raise ValueError(
            "No vault repo configured. Pass --vault-repo <url> on first use."
        )

    vault_local = Path.home() / ".local" / "share" / "ai-memory-vault" / "vault"
    vault_local.parent.mkdir(parents=True, exist_ok=True)

    if not (vault_local / ".git").exists():
        code, out = _run(["git", "clone", vault_repo, str(vault_local)], cwd=Path.home())
        if code != 0:
            # If clone fails (e.g. empty repo), init locally and set remote
            _run(["git", "init"], cwd=vault_local)
            _run(["git", "remote", "add", "origin", vault_repo], cwd=vault_local)
    else:
        _run(["git", "pull", "--rebase", "origin", "main"], cwd=vault_local)

    # Copy exports into vault
    import shutil
    dest = vault_local / "exports"
    if export_dir.exists():
        shutil.copytree(str(export_dir), str(dest), dirs_exist_ok=True)

    _run(["git", "add", "-A"], cwd=vault_local)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    commit_msg = message or f"vault: export snapshot {ts}"
    code, out = _run(["git", "commit", "-m", commit_msg], cwd=vault_local)
    if code != 0 and "nothing to commit" in out:
        return "nothing to commit"

    push_code, push_out = _run(["git", "push", "-u", "origin", "main"], cwd=vault_local)
    if push_code != 0:
        # Try pushing to master as fallback
        _run(["git", "push", "-u", "origin", "HEAD:main", "--force-with-lease"], cwd=vault_local)

    return commit_msg
