from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_memory_vault import config
from ai_memory_vault.agents.base import AgentAdapter, NativeSessionFile
from ai_memory_vault.agents.registry import AgentRegistry
from ai_memory_vault.domain.models import Session
from ai_memory_vault.infrastructure.sync import git as sync


def write_jsonl(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n")


class RawSessionSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name)
        self.vault = self.home / "vault"
        self.claude_dir = self.home / ".claude" / "projects"
        self.codex_dir = self.home / ".codex"
        self.codex_sessions = self.codex_dir / "sessions"
        self.codex_index = self.codex_dir / "session_index.jsonl"
        self.path_map = self.home / ".config" / "path-map.json"
        self.search_dirs = [self.home / "repos", self.home / "work"]
        self.patchers = [
            patch.object(config, "HOME", self.home),
            patch.object(config, "CLAUDE_PROJECTS_DIR", self.claude_dir),
            patch.object(config, "CODEX_SESSIONS_DIR", self.codex_sessions),
            patch.object(config, "CODEX_SESSION_INDEX", self.codex_index),
            patch.object(config, "PATH_MAP_FILE", self.path_map),
            patch.object(config, "DEFAULT_SEARCH_DIRS", self.search_dirs),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.temp_dir.cleanup()

    def test_backup_and_restore_both_sources_for_resume(self) -> None:
        health = self.home / "repos" / "health-family-tracker"
        dream = self.home / "repos" / "dream-home"
        health.mkdir(parents=True)
        dream.mkdir(parents=True)

        claude_id = "11111111-1111-4111-8111-111111111111"
        claude_slug = str(health).replace("/", "-")
        claude_file = self.claude_dir / claude_slug / f"{claude_id}.jsonl"
        write_jsonl(
            claude_file,
            [
                {
                    "type": "user",
                    "sessionId": claude_id,
                    "cwd": str(health),
                    "message": {"content": "hello"},
                }
            ],
        )

        codex_id = "22222222-2222-4222-8222-222222222222"
        codex_file = (
            self.codex_sessions
            / "2026"
            / "06"
            / "17"
            / f"rollout-2026-06-17T00-00-00-{codex_id}.jsonl"
        )
        write_jsonl(
            codex_file,
            [
                {
                    "timestamp": "2026-06-17T00:00:00Z",
                    "type": "session_meta",
                    "payload": {"id": codex_id, "cwd": str(dream)},
                }
            ],
        )
        self.codex_index.parent.mkdir(parents=True, exist_ok=True)
        self.codex_index.write_text(
            json.dumps({"id": codex_id, "thread_name": "Dream work"}) + "\n"
        )

        sessions = [
            Session(claude_id, "claude", "repos/health-family-tracker", "health", None, None),
            Session(codex_id, "codex", "repos/dream-home", "dream", None, None),
        ]
        result = sync.backup_raw_sessions(self.vault, sessions=sessions)
        self.assertEqual((result.claude, result.codex), (1, 1))

        manifest = json.loads((self.vault / "raw" / "manifest.json").read_text())
        projects = {item["project_rel_path"] for item in manifest["sessions"]}
        self.assertEqual(projects, {"repos/health-family-tracker", "repos/dream-home"})

        claude_file.unlink()
        codex_file.unlink()
        self.codex_index.unlink()
        restored, conflicts = sync.restore_raw_sessions(self.vault)

        self.assertEqual(conflicts, 0)
        self.assertEqual({item.source for item in restored}, {"claude", "codex"})
        self.assertTrue(claude_file.exists())
        self.assertTrue(codex_file.exists())
        self.assertIn(str(health), claude_file.read_text())
        self.assertIn(str(dream), codex_file.read_text())
        self.assertIn(codex_id, self.codex_index.read_text())

        repeated, repeated_conflicts = sync.restore_raw_sessions(self.vault)
        self.assertEqual(repeated, [])
        self.assertEqual(repeated_conflicts, 0)

    def test_legacy_claude_backup_uses_json_cwd_not_lossy_path(self) -> None:
        project = self.home / "repos" / "health-family-tracker"
        project.mkdir(parents=True)
        session_id = "33333333-3333-4333-8333-333333333333"
        legacy = (
            self.vault
            / "raw"
            / "claude"
            / "repos"
            / "health"
            / "family"
            / "tracker"
            / f"{session_id}.jsonl"
        )
        write_jsonl(
            legacy,
            [
                {
                    "type": "user",
                    "sessionId": session_id,
                    "cwd": "/home/alice/repos/health-family-tracker",
                    "message": {"content": "legacy"},
                }
            ],
        )

        restored, conflicts = sync.restore_raw_sessions(self.vault, sources={"claude"})

        expected_slug = str(project).replace("/", "-")
        destination = self.claude_dir / expected_slug / f"{session_id}.jsonl"
        self.assertEqual(conflicts, 0)
        self.assertEqual(len(restored), 1)
        self.assertTrue(destination.exists())
        self.assertIn(str(project), destination.read_text())
        self.assertNotIn("health/family/tracker", str(destination))

    def test_restore_never_overwrites_different_existing_session(self) -> None:
        project = self.home / "repos" / "dream-home"
        project.mkdir(parents=True)
        session_id = "44444444-4444-4444-8444-444444444444"
        raw_path = (
            self.vault
            / "raw"
            / "codex"
            / "sessions"
            / "2026"
            / "01"
            / "01"
            / f"rollout-{session_id}.jsonl"
        )
        write_jsonl(
            raw_path,
            [
                {
                    "type": "session_meta",
                    "payload": {"id": session_id, "cwd": "/home/alice/repos/dream-home"},
                }
            ],
        )
        manifest = {
            "version": 2,
            "sessions": [
                {
                    "source": "codex",
                    "session_id": session_id,
                    "raw_path": str(raw_path.relative_to(self.vault)),
                    "project_rel_path": "repos/dream-home",
                    "original_cwd": "/home/alice/repos/dream-home",
                    "original_project_root": "/home/alice/repos/dream-home",
                }
            ],
        }
        manifest_path = self.vault / "raw" / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest))

        destination = self.codex_sessions / "2026" / "01" / "01" / f"rollout-{session_id}.jsonl"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("local content\n")

        restored, conflicts = sync.restore_raw_sessions(self.vault, sources={"codex"})

        self.assertEqual(restored, [])
        self.assertEqual(conflicts, 1)
        self.assertEqual(destination.read_text(), "local content\n")

    def test_restore_rejects_manifest_path_outside_vault(self) -> None:
        manifest = {
            "version": 2,
            "sessions": [
                {
                    "source": "codex",
                    "session_id": "unsafe",
                    "raw_path": "../../outside.jsonl",
                    "project_rel_path": "repos/project",
                    "original_cwd": "/home/alice/repos/project",
                    "original_project_root": "/home/alice/repos/project",
                }
            ],
        }
        manifest_path = self.vault / "raw" / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest))

        restored, conflicts = sync.restore_raw_sessions(self.vault)

        self.assertEqual(restored, [])
        self.assertEqual(conflicts, 1)

    def test_new_agent_works_by_registration_without_sync_changes(self) -> None:
        source_root = self.home / ".future-agent" / "sessions"
        destination_root = self.home / ".future-agent" / "restored"
        session_id = "future-session"
        source_file = source_root / f"{session_id}.jsonl"
        write_jsonl(
            source_file,
            [{"session": session_id, "cwd": str(self.home / "repos" / "future-app")}],
        )
        (self.home / "repos" / "future-app").mkdir(parents=True)

        class FutureAgent(AgentAdapter):
            source = "future"
            label = "Future Agent"
            aliases = ("future-cli",)

            def extract_sessions(self):
                return []

            def iter_local_native_sessions(self):
                return [
                    NativeSessionFile(
                        source_path=source_file,
                        session_id=session_id,
                        cwd=str(self_home / "repos" / "future-app"),
                        vault_relative_path=Path("raw/future") / source_file.name,
                    )
                ]

            def discover_vault_native_sessions(self, vault_local):
                return []

            def restore_destination(self, native_file, project_root):
                return destination_root / native_file.source_path.name

        self_home = self.home
        registry = AgentRegistry([FutureAgent()])
        with patch.object(sync, "AGENTS", registry):
            result = sync.backup_raw_sessions(self.vault, sources={"future-cli"})
            source_file.unlink()
            restored, conflicts = sync.restore_raw_sessions(self.vault, sources={"future"})

        self.assertEqual(result.count("future"), 1)
        self.assertEqual(conflicts, 0)
        self.assertEqual(len(restored), 1)
        self.assertTrue((destination_root / source_file.name).exists())

    def test_home_directory_is_normalized_to_home_label(self) -> None:
        self.assertEqual(sync._portable_rel_path(str(self.home)), "home")
        self.assertEqual(sync._portable_rel_path("."), "home")
        self.assertEqual(sync._portable_rel_path("/home/another-user"), "home")
        self.assertEqual(sync._project_root("home"), self.home)


if __name__ == "__main__":
    unittest.main()
