"""Claude Code integration."""

from __future__ import annotations

import json
from pathlib import Path

from .. import config
from ..infrastructure.extractors.claude import extract_all
from .base import AgentAdapter, NativeSessionFile


def _identity(path: Path) -> tuple[str, str]:
    session_id = path.stem
    cwd = ""
    for raw in path.read_text(errors="replace").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        session_id = str(event.get("sessionId") or session_id)
        cwd = str(event.get("cwd") or cwd)
        if session_id and cwd:
            break
    return session_id, cwd


class ClaudeAgentAdapter(AgentAdapter):
    source = "claude"
    label = "Claude Code"
    aliases = ("claude-code",)
    color = "blue"

    def extract_sessions(self):
        return extract_all()

    def native_data_root(self) -> Path:
        return config.CLAUDE_PROJECTS_DIR

    def iter_local_native_sessions(self) -> list[NativeSessionFile]:
        root = self.native_data_root()
        if not root.exists():
            return []
        files: list[NativeSessionFile] = []
        for project_dir in sorted(root.iterdir()):
            if not project_dir.is_dir():
                continue
            for path in sorted(project_dir.glob("*.jsonl")):
                session_id, cwd = _identity(path)
                files.append(
                    NativeSessionFile(
                        source_path=path,
                        session_id=session_id,
                        cwd=cwd,
                        vault_relative_path=(
                            Path(config.VAULT_RAW_CLAUDE_PROJECTS_SUBDIR)
                            / project_dir.name
                            / path.name
                        ),
                    )
                )
        return files

    def discover_vault_native_sessions(self, vault_local: Path) -> list[NativeSessionFile]:
        legacy_root = vault_local / config.VAULT_RAW_CLAUDE_SUBDIR
        current_root = vault_local / config.VAULT_RAW_CLAUDE_PROJECTS_SUBDIR
        if not legacy_root.exists():
            return []
        files: list[NativeSessionFile] = []
        for path in legacy_root.rglob("*.jsonl"):
            if path.is_relative_to(current_root):
                continue
            session_id, cwd = _identity(path)
            files.append(
                NativeSessionFile(
                    source_path=path,
                    session_id=session_id,
                    cwd=cwd,
                    vault_relative_path=path.relative_to(vault_local),
                    project_rel_path="",
                    original_project_root=cwd,
                )
            )
        return files

    def restore_destination(
        self,
        native_file: NativeSessionFile,
        project_root: Path,
    ) -> Path:
        slug = str(project_root).replace("/", "-")
        return config.CLAUDE_PROJECTS_DIR / slug / native_file.source_path.name
