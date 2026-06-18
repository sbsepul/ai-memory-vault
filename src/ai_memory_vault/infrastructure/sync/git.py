"""Git-backed storage for portable exports and resumable native sessions."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ... import config
from ...agents import AGENTS
from ...agents.base import AgentAdapter, NativeSessionFile
from ...utils import read_git_remote

if TYPE_CHECKING:
    from ...domain.models import Session

RAW_MANIFEST_VERSION = 2


@dataclass(frozen=True)
class RawSessionRecord:
    source: str
    session_id: str
    raw_path: str
    project_rel_path: str
    original_cwd: str
    original_project_root: str

    def as_native_file(self, vault_local: Path) -> NativeSessionFile:
        return NativeSessionFile(
            source_path=_safe_child(vault_local, self.raw_path),
            session_id=self.session_id,
            cwd=self.original_cwd,
            vault_relative_path=Path(self.raw_path),
            project_rel_path=self.project_rel_path,
            original_project_root=self.original_project_root,
        )


@dataclass(frozen=True)
class RawBackupResult:
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def count(self, source: str) -> int:
        return self.counts.get(source, 0)

    @property
    def claude(self) -> int:
        return self.count("claude")

    @property
    def codex(self) -> int:
        return self.count("codex")


@dataclass(frozen=True)
class RestoredSession:
    source: str
    session_id: str
    project_rel_path: str
    destination: str


def _safe_child(root: Path, relative_path: str | Path) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute():
        raise ValueError(f"Expected a relative path, got: {relative}")
    resolved_root = root.resolve()
    child = root / relative
    resolved_child = child.resolve()
    if not resolved_child.is_relative_to(resolved_root):
        raise ValueError(f"Path escapes its allowed root: {relative}")
    return child


def _project_root(project_rel_path: str) -> Path:
    if project_rel_path in {"", ".", "home"}:
        return config.HOME
    return _safe_child(config.HOME, project_rel_path)


def load_config() -> dict:
    if config.CONFIG_FILE.exists():
        return json.loads(config.CONFIG_FILE.read_text())
    return {}


def save_config(data: dict) -> None:
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.CONFIG_FILE.write_text(json.dumps(data, indent=2))


def _run(command: list[str], cwd: Path) -> tuple[int, str]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def _resolve_vault_repo(vault_repo: str | None) -> str:
    settings = load_config()
    if vault_repo:
        settings["vault_repo"] = vault_repo
        save_config(settings)
        return vault_repo
    if "vault_repo" in settings:
        return settings["vault_repo"]
    raise ValueError("No vault repo configured. Pass --vault-repo <url> on first use.")


def _default_branch(vault_local: Path) -> str:
    code, output = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=vault_local)
    branch = output.strip()
    return branch if code == 0 and branch and branch != "HEAD" else "main"


def _ensure_vault_local(vault_repo: str) -> Path:
    config.VAULT_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    if not (config.VAULT_LOCAL / ".git").exists():
        code, _ = _run(
            ["git", "clone", vault_repo, str(config.VAULT_LOCAL)],
            cwd=config.HOME,
        )
        if code != 0:
            config.VAULT_LOCAL.mkdir(parents=True, exist_ok=True)
            _run(["git", "init", "-b", "main"], cwd=config.VAULT_LOCAL)
            _run(["git", "remote", "add", "origin", vault_repo], cwd=config.VAULT_LOCAL)
    else:
        branch = _default_branch(config.VAULT_LOCAL)
        _run(["git", "pull", "--rebase", "origin", branch], cwd=config.VAULT_LOCAL)
    return config.VAULT_LOCAL


def _portable_rel_path(cwd: str) -> str:
    def normalized(value: str) -> str:
        return "home" if value in {"", "."} else value

    path = Path(cwd).expanduser()
    if not path.is_absolute():
        return normalized(str(path))
    try:
        return normalized(str(path.relative_to(config.HOME)))
    except ValueError:
        pass
    parts = path.parts
    home_prefix_lengths = {"Users": 3, "home": 3, "root": 2}
    prefix_length = home_prefix_lengths.get(parts[1], 0) if len(parts) > 1 else 0
    if prefix_length:
        return normalized(str(Path(*parts[prefix_length:])))
    return normalized(str(path).lstrip("/"))


def _load_raw_manifest(vault_local: Path) -> dict[tuple[str, str], RawSessionRecord]:
    path = vault_local / config.VAULT_RAW_MANIFEST
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    records: dict[tuple[str, str], RawSessionRecord] = {}
    for item in payload.get("sessions", []):
        try:
            record = RawSessionRecord(**item)
            canonical_source = AGENTS.canonical_source(record.source)
            record = RawSessionRecord(**{**asdict(record), "source": canonical_source})
        except (TypeError, ValueError):
            continue
        records[(record.source, record.session_id)] = record
    return records


def _write_raw_manifest(
    vault_local: Path,
    records: dict[tuple[str, str], RawSessionRecord],
) -> None:
    path = vault_local / config.VAULT_RAW_MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": RAW_MANIFEST_VERSION,
        "sessions": [
            asdict(record)
            for record in sorted(
                records.values(),
                key=lambda item: (item.source, item.session_id),
            )
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_repo_manifest(sessions: list[Session], vault_local: Path) -> int:
    manifest = {
        session.project_rel_path: session.git_remote for session in sessions if session.git_remote
    }
    if not manifest:
        return 0
    (vault_local / config.VAULT_REPO_MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True)
    )
    return len(manifest)


def _session_lookup(
    sessions: list[Session] | None,
) -> dict[tuple[str, str], Session]:
    lookup: dict[tuple[str, str], Session] = {}
    for session in sessions or []:
        try:
            source = AGENTS.canonical_source(session.source)
        except ValueError:
            continue
        lookup[(source, session.id)] = session
    return lookup


def _record_from_native(
    adapter: AgentAdapter,
    native_file: NativeSessionFile,
    session: Session | None,
) -> RawSessionRecord:
    project_rel_path = (
        session.project_rel_path
        if session
        else native_file.project_rel_path
        or (_portable_rel_path(native_file.cwd) if native_file.cwd else "home")
    )
    original_project_root = native_file.original_project_root or str(
        _project_root(project_rel_path)
    )
    return RawSessionRecord(
        source=adapter.source,
        session_id=native_file.session_id,
        raw_path=str(native_file.vault_relative_path),
        project_rel_path=project_rel_path,
        original_cwd=native_file.cwd,
        original_project_root=original_project_root,
    )


def backup_raw_sessions(
    vault_local: Path,
    sessions: list[Session] | None = None,
    sources: set[str] | None = None,
) -> RawBackupResult:
    """Back up native session files through registered agent adapters."""
    lookup = _session_lookup(sessions)
    records = _load_raw_manifest(vault_local)
    counts: dict[str, int] = {}

    for adapter in AGENTS.select(sources):
        count = 0
        for native_file in adapter.iter_local_native_sessions():
            session = lookup.get((adapter.source, native_file.session_id))
            record = _record_from_native(adapter, native_file, session)
            destination = _safe_child(vault_local, record.raw_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(native_file.source_path, destination)
            records[(adapter.source, native_file.session_id)] = record
            count += 1
        adapter.backup_auxiliary(vault_local)
        counts[adapter.source] = count

    _write_raw_manifest(vault_local, records)
    return RawBackupResult(counts=counts)


def backup_raw_claude(vault_local: Path) -> int:
    """Compatibility wrapper for the original Claude-only API."""
    return backup_raw_sessions(vault_local, sources={"claude"}).count("claude")


def _normalize_remote(url: str) -> str:
    cleaned = re.sub(r"\.git$", "", url.strip())
    parts = re.split(r"[:/]", cleaned)
    return "/".join(parts[-2:]).lower() if len(parts) >= 2 else cleaned.lower()


def _load_path_map() -> dict[str, str]:
    if not config.PATH_MAP_FILE.exists():
        return {}
    try:
        value = json.loads(config.PATH_MAP_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _local_repo_index() -> tuple[dict[str, str], dict[str, list[str]]]:
    by_remote: dict[str, str] = {}
    by_name: dict[str, list[str]] = {}
    for root in config.DEFAULT_SEARCH_DIRS:
        if not root.exists():
            continue
        for git_dir in root.rglob(".git"):
            repo = git_dir.parent
            try:
                relative_path = str(repo.relative_to(config.HOME))
            except ValueError:
                continue
            by_name.setdefault(repo.name.lower(), []).append(relative_path)
            remote = read_git_remote(repo)
            if remote:
                by_remote[_normalize_remote(remote)] = relative_path
    return by_remote, by_name


def _resolve_project_path(
    project_rel_path: str,
    vault_local: Path,
    repo_index: tuple[dict[str, str], dict[str, list[str]]],
) -> str:
    mapped = _load_path_map().get(project_rel_path, project_rel_path)
    if _project_root(mapped).exists():
        return mapped

    by_remote, by_name = repo_index
    manifest_path = vault_local / config.VAULT_REPO_MANIFEST
    try:
        remotes = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        remotes = {}
    remote = remotes.get(project_rel_path)
    remote_match = by_remote.get(_normalize_remote(remote)) if remote else None
    if remote_match:
        return remote_match

    candidates = by_name.get(Path(project_rel_path).name.lower(), [])
    return candidates[0] if len(candidates) == 1 else mapped


def _discover_unmanifested(
    vault_local: Path,
    known: set[tuple[str, str]],
) -> list[RawSessionRecord]:
    records: list[RawSessionRecord] = []
    for adapter in AGENTS.select():
        for native_file in adapter.discover_vault_native_sessions(vault_local):
            key = (adapter.source, native_file.session_id)
            if key in known:
                continue
            record = _record_from_native(adapter, native_file, session=None)
            records.append(record)
            known.add(key)
    return records


def _replace_path(value: str, old_root: str, new_root: str) -> str:
    normalized_root = old_root.rstrip("/")
    if normalized_root and (value == normalized_root or value.startswith(normalized_root + "/")):
        return new_root.rstrip("/") + value[len(normalized_root) :]
    return value


def _rewrite_location_fields(value: Any, old_root: str, new_root: str) -> Any:
    if isinstance(value, list):
        return [_rewrite_location_fields(item, old_root, new_root) for item in value]
    if not isinstance(value, dict):
        return value

    path_field_handlers = {
        "cwd": lambda item: _replace_path(item, old_root, new_root),
        "workspace_roots": lambda item: [
            _replace_path(root, old_root, new_root) if isinstance(root, str) else root
            for root in item
        ],
    }
    rewritten: dict[str, Any] = {}
    for key, item in value.items():
        handler = path_field_handlers.get(key)
        can_handle = (key == "cwd" and isinstance(item, str)) or (
            key == "workspace_roots" and isinstance(item, list)
        )
        rewritten[key] = (
            handler(item)
            if handler and can_handle
            else _rewrite_location_fields(item, old_root, new_root)
        )
    return rewritten


def _render_restored_jsonl(source: Path, old_root: str, new_root: str) -> bytes:
    output: list[str] = []
    for raw in source.read_text(errors="replace").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            output.append(raw)
            continue
        rewritten = _rewrite_location_fields(event, old_root, new_root)
        output.append(json.dumps(rewritten, ensure_ascii=False, separators=(",", ":")))
    return (("\n".join(output) + "\n") if output else "").encode()


def _same_content(path: Path, content: bytes) -> bool:
    if not path.exists():
        return False
    local_hash = _semantic_jsonl_hash(path.read_bytes())
    restored_hash = _semantic_jsonl_hash(content)
    return local_hash == restored_hash


def _semantic_jsonl_hash(content: bytes) -> bytes:
    normalized: list[bytes] = []
    for line in content.decode(errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            normalized.append(line.encode())
            continue
        normalized.append(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        )
    return hashlib.sha256(b"\n".join(normalized)).digest()


def restore_raw_sessions(
    vault_local: Path,
    sources: set[str] | None = None,
    dry_run: bool = False,
) -> tuple[list[RestoredSession], int]:
    """Restore native sessions without agent-specific branches in the core."""
    selected_adapters = AGENTS.select(sources)
    selected_sources = {adapter.source for adapter in selected_adapters}
    records_by_key = _load_raw_manifest(vault_local)
    records = list(records_by_key.values())
    records.extend(_discover_unmanifested(vault_local, set(records_by_key)))

    restored: list[RestoredSession] = []
    conflicts = 0
    repo_index = _local_repo_index()
    restored_ids = {adapter.source: set() for adapter in selected_adapters}

    for record in records:
        if record.source not in selected_sources:
            continue
        adapter = AGENTS.get(record.source)
        try:
            native_file = record.as_native_file(vault_local)
        except ValueError:
            conflicts += 1
            continue
        if not native_file.source_path.exists():
            continue

        try:
            project_rel_path = _resolve_project_path(
                record.project_rel_path,
                vault_local,
                repo_index,
            )
            project_root = _project_root(project_rel_path)
        except ValueError:
            conflicts += 1
            continue
        destination = adapter.restore_destination(native_file, project_root)
        content = _render_restored_jsonl(
            native_file.source_path,
            record.original_project_root or record.original_cwd,
            str(project_root),
        )
        if destination.exists():
            conflicts += int(not _same_content(destination, content))
            continue

        restored.append(
            RestoredSession(
                source=adapter.source,
                session_id=record.session_id,
                project_rel_path=project_rel_path,
                destination=str(destination),
            )
        )
        restored_ids[adapter.source].add(record.session_id)
        if dry_run:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(destination)

    for adapter in selected_adapters:
        adapter.restore_auxiliary(
            vault_local,
            restored_ids[adapter.source],
            dry_run,
        )
    return restored, conflicts


def restore_raw_claude(vault_local: Path, dry_run: bool = False) -> list[tuple[str, str]]:
    """Compatibility wrapper returning the original tuple shape."""
    restored, _ = restore_raw_sessions(vault_local, {"claude"}, dry_run)
    return [(item.project_rel_path, Path(item.destination).parent.name) for item in restored]


def _clone_repos(vault_local: Path, dry_run: bool = False) -> list[tuple[str, str]]:
    manifest_path = vault_local / config.VAULT_REPO_MANIFEST
    if not manifest_path.exists():
        return []
    manifest: dict[str, str] = json.loads(manifest_path.read_text())
    cloned: list[tuple[str, str]] = []
    for relative_path, remote_url in manifest.items():
        try:
            project_dir = _project_root(relative_path)
        except ValueError:
            continue
        if project_dir.exists():
            continue
        if dry_run:
            cloned.append((relative_path, remote_url))
            continue
        project_dir.parent.mkdir(parents=True, exist_ok=True)
        code, _ = _run(["git", "clone", remote_url, str(project_dir)], cwd=config.HOME)
        if code == 0:
            cloned.append((relative_path, remote_url))
    return cloned


def _backup_summary(result: RawBackupResult) -> str:
    parts = [
        f"+{count} {AGENTS.get(source).label}"
        for source, count in sorted(result.counts.items())
        if count
    ]
    return f" ({', '.join(parts)} native files)" if parts else ""


def push_to_vault(
    export_dir: Path,
    vault_repo: str | None,
    *,
    include_raw: bool = False,
    message: str | None = None,
    sessions: list[Session] | None = None,
) -> str:
    resolved_repo = _resolve_vault_repo(vault_repo)
    vault_local = _ensure_vault_local(resolved_repo)
    if export_dir.exists():
        shutil.copytree(
            str(export_dir),
            str(vault_local / config.VAULT_EXPORTS_SUBDIR),
            dirs_exist_ok=True,
        )

    raw_result = RawBackupResult()
    if include_raw:
        sources = {session.source for session in sessions or []} or None
        raw_result = backup_raw_sessions(vault_local, sessions=sessions, sources=sources)
    if sessions:
        _write_repo_manifest(sessions, vault_local)

    _run(["git", "add", "-A"], cwd=vault_local)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    commit_message = message or (f"vault: export snapshot {timestamp}{_backup_summary(raw_result)}")
    code, output = _run(["git", "commit", "-m", commit_message], cwd=vault_local)
    if code != 0 and "nothing to commit" in output:
        return "nothing to commit"
    if code != 0:
        raise RuntimeError(f"Vault commit failed: {output.strip()}")

    branch = _default_branch(vault_local)
    push_code, push_output = _run(
        ["git", "push", "-u", "origin", branch],
        cwd=vault_local,
    )
    if push_code != 0:
        raise RuntimeError(f"Vault push failed: {push_output.strip()}")
    return commit_message


class PullResult:
    def __init__(self) -> None:
        self.export_files = 0
        self.restored_raw: list[RestoredSession] = []
        self.restore_conflicts = 0
        self.cloned_repos: list[tuple[str, str]] = []
        self.vault_local = config.VAULT_LOCAL

    @property
    def restored_sessions(self) -> list[tuple[str, str]]:
        return [
            (item.project_rel_path, Path(item.destination).parent.name)
            for item in self.restored_raw
            if item.source == AGENTS.canonical_source("claude")
        ]


def pull_from_vault(
    vault_repo: str | None,
    output_dir: Path,
    *,
    restore_raw: bool = False,
    restore_sources: set[str] | None = None,
    restore_claude: bool = False,
    restore_codex: bool = False,
    clone_repos: bool = False,
    dry_run: bool = False,
) -> PullResult:
    resolved_repo = _resolve_vault_repo(vault_repo)
    result = PullResult()
    vault_local = _ensure_vault_local(resolved_repo)
    result.vault_local = vault_local

    exports_src = vault_local / config.VAULT_EXPORTS_SUBDIR
    if exports_src.exists():
        result.export_files = sum(1 for _ in exports_src.rglob("*.md"))
        if not dry_run:
            shutil.copytree(str(exports_src), str(output_dir), dirs_exist_ok=True)

    legacy_flags = {"claude": restore_claude, "codex": restore_codex}
    requested_sources = set(restore_sources or ())
    requested_sources.update(source for source, enabled in legacy_flags.items() if enabled)
    should_restore = restore_raw or bool(requested_sources)
    if should_restore:
        selected = None if restore_raw else requested_sources
        result.restored_raw, result.restore_conflicts = restore_raw_sessions(
            vault_local,
            sources=selected,
            dry_run=dry_run,
        )
    if clone_repos:
        result.cloned_repos = _clone_repos(vault_local, dry_run=dry_run)
    return result
