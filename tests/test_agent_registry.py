from __future__ import annotations

import unittest
from pathlib import Path

from ai_memory_vault.agents.base import AgentAdapter, NativeSessionFile
from ai_memory_vault.agents.registry import AgentRegistry
from ai_memory_vault.domain.models import Message, Session
from ai_memory_vault.domain.project_tree import build_tree


class StubAgent(AgentAdapter):
    source = "stub"
    label = "Stub Agent"
    aliases = ("stub-cli",)
    color = "magenta"

    def extract_sessions(self):
        return []

    def iter_local_native_sessions(self):
        return []

    def discover_vault_native_sessions(self, vault_local):
        return []

    def restore_destination(
        self,
        native_file: NativeSessionFile,
        project_root: Path,
    ) -> Path:
        return project_root / native_file.source_path.name


class AgentRegistryTests(unittest.TestCase):
    def test_aliases_resolve_to_one_canonical_source(self) -> None:
        registry = AgentRegistry([StubAgent()])

        self.assertEqual(registry.canonical_source("stub-cli"), "stub")
        self.assertEqual(registry.get("stub-cli").label, "Stub Agent")
        self.assertIn("stub-cli", registry.choices())

    def test_project_tree_aggregates_unregistered_source_names_generically(self) -> None:
        session = Session(
            id="session",
            source="future-agent",
            project_rel_path="repos/future",
            name="future",
            started_at=None,
            updated_at=None,
            messages=[Message(role="user", content="hello")],
        )

        node = build_tree([session])["repos/future"]

        self.assertEqual(node.stats_for("future-agent").sessions, 1)
        self.assertEqual(node.stats_for("future-agent").messages, 1)
        self.assertEqual(node.total_sessions, 1)


if __name__ == "__main__":
    unittest.main()
