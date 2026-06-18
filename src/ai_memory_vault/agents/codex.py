"""Codex CLI integration."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .. import config
from ..infrastructure.extractors.codex import extract_all
from .base import AgentAdapter, NativeSessionFile


def _identity(path: Path) -> tuple[str, str]:
    session_id = path.stem
    cwd = ""
    for raw in path.read_text(errors="replace").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        payload = event.get("payload", {})
        if event.get("type") != "session_meta" or not isinstance(payload, dict):
            continue
        session_id = str(payload.get("id") or event.get("id") or session_id)
        cwd = str(payload.get("cwd") or cwd)
        break
    return session_id, cwd


class CodexAgentAdapter(AgentAdapter):
    source = "codex"
    label = "Codex CLI"
    aliases = ("codex-cli", "openai-codex")
    color = "green"

    def extract_sessions(self):
        return extract_all()

    def native_data_root(self) -> Path:
        return config.CODEX_SESSIONS_DIR

    def iter_local_native_sessions(self) -> list[NativeSessionFile]:
        root = self.native_data_root()
        if not root.exists():
            return []
        files: list[NativeSessionFile] = []
        for path in sorted(root.rglob("*.jsonl")):
            session_id, cwd = _identity(path)
            files.append(
                NativeSessionFile(
                    source_path=path,
                    session_id=session_id,
                    cwd=cwd,
                    vault_relative_path=(
                        Path(config.VAULT_RAW_CODEX_SESSIONS_SUBDIR) / path.relative_to(root)
                    ),
                )
            )
        return files

    def discover_vault_native_sessions(self, vault_local: Path) -> list[NativeSessionFile]:
        root = vault_local / config.VAULT_RAW_CODEX_SESSIONS_SUBDIR
        if not root.exists():
            return []
        files: list[NativeSessionFile] = []
        for path in root.rglob("*.jsonl"):
            session_id, cwd = _identity(path)
            files.append(
                NativeSessionFile(
                    source_path=path,
                    session_id=session_id,
                    cwd=cwd,
                    vault_relative_path=path.relative_to(vault_local),
                )
            )
        return files

    def restore_destination(
        self,
        native_file: NativeSessionFile,
        project_root: Path,
    ) -> Path:
        prefix = Path(config.VAULT_RAW_CODEX_SESSIONS_SUBDIR)
        try:
            relative_path = native_file.vault_relative_path.relative_to(prefix)
        except ValueError:
            relative_path = Path(native_file.source_path.name)
        return config.CODEX_SESSIONS_DIR / relative_path

    def backup_auxiliary(self, vault_local: Path) -> None:
        if not config.CODEX_SESSION_INDEX.exists():
            return
        destination = vault_local / config.VAULT_RAW_CODEX_SUBDIR / "session_index.jsonl"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config.CODEX_SESSION_INDEX, destination)

    def restore_auxiliary(
        self,
        vault_local: Path,
        restored_session_ids: set[str],
        dry_run: bool,
    ) -> None:
        source = vault_local / config.VAULT_RAW_CODEX_SUBDIR / "session_index.jsonl"
        if not source.exists() or not restored_session_ids:
            return

        existing_lines = (
            config.CODEX_SESSION_INDEX.read_text(errors="replace").splitlines()
            if config.CODEX_SESSION_INDEX.exists()
            else []
        )
        existing_ids = self._index_ids(existing_lines)
        additions = [
            line
            for line in source.read_text(errors="replace").splitlines()
            if self._index_id(line) in restored_session_ids
            and self._index_id(line) not in existing_ids
        ]
        if not additions or dry_run:
            return
        config.CODEX_SESSION_INDEX.parent.mkdir(parents=True, exist_ok=True)
        prefix = (
            "\n"
            if config.CODEX_SESSION_INDEX.exists() and config.CODEX_SESSION_INDEX.stat().st_size
            else ""
        )
        with config.CODEX_SESSION_INDEX.open("a", encoding="utf-8") as handle:
            handle.write(prefix + "\n".join(additions) + "\n")

    @staticmethod
    def _index_id(line: str) -> str:
        try:
            return str(json.loads(line).get("id", ""))
        except json.JSONDecodeError:
            return ""

    def _index_ids(self, lines: list[str]) -> set[str]:
        return {session_id for line in lines if (session_id := self._index_id(line))}
