"""Contracts shared by all CLI agent integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..domain.models import Session


@dataclass(frozen=True)
class NativeSessionFile:
    source_path: Path
    session_id: str
    cwd: str
    vault_relative_path: Path
    project_rel_path: str = ""
    original_project_root: str = ""


class AgentAdapter(ABC):
    """One extension point for discovery, display, backup, and native restore."""

    source: str
    label: str
    aliases: tuple[str, ...] = ()
    color: str = "white"

    @abstractmethod
    def extract_sessions(self) -> list[Session]:
        """Return normalized sessions available on this machine."""

    @abstractmethod
    def iter_local_native_sessions(self) -> list[NativeSessionFile]:
        """Return native files required by the agent's resume command."""

    @abstractmethod
    def discover_vault_native_sessions(self, vault_local: Path) -> list[NativeSessionFile]:
        """Return native vault files absent from the central manifest."""

    @abstractmethod
    def restore_destination(
        self,
        native_file: NativeSessionFile,
        project_root: Path,
    ) -> Path:
        """Return the machine-local destination for a restored native file."""

    def backup_auxiliary(self, vault_local: Path) -> None:
        """Back up optional agent metadata such as a session-name index."""

    def restore_auxiliary(
        self,
        vault_local: Path,
        restored_session_ids: set[str],
        dry_run: bool,
    ) -> None:
        """Restore optional metadata after native session files are restored."""

    def native_data_root(self) -> Path | None:
        """Return the agent's native session directory when one exists."""
        return None
