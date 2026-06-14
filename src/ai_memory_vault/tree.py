"""Build a project tree showing which directories have AI conversation history."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .extractors.models import Session


@dataclass
class ProjectNode:
    rel_path: str
    has_git: bool = False
    claude_sessions: int = 0
    codex_sessions: int = 0
    claude_messages: int = 0
    codex_messages: int = 0

    @property
    def total_sessions(self) -> int:
        return self.claude_sessions + self.codex_sessions

    @property
    def total_messages(self) -> int:
        return self.claude_messages + self.codex_messages


def build_tree(sessions: list[Session]) -> dict[str, ProjectNode]:
    """Return a flat map of rel_path -> ProjectNode."""
    nodes: dict[str, ProjectNode] = {}

    for s in sessions:
        path = s.project_rel_path or "(root)"
        if path not in nodes:
            nodes[path] = ProjectNode(rel_path=path, has_git=s.has_git)
        node = nodes[path]
        node.has_git = node.has_git or s.has_git
        if s.source == "claude":
            node.claude_sessions += 1
            node.claude_messages += s.message_count
        else:
            node.codex_sessions += 1
            node.codex_messages += s.message_count

    return dict(sorted(nodes.items()))


def render_tree(nodes: dict[str, ProjectNode]) -> str:
    """Render the project tree as a plain-text summary."""
    lines = ["AI Memory Vault — Project Tree", "=" * 50, ""]

    for path, node in nodes.items():
        git_tag = "[git]" if node.has_git else "[no-git]"
        lines.append(f"{path}  {git_tag}")

        if node.claude_sessions:
            lines.append(f"  claude : {node.claude_sessions} sessions, {node.claude_messages} msgs")
        if node.codex_sessions:
            lines.append(f"  codex  : {node.codex_sessions} sessions, {node.codex_messages} msgs")
        lines.append("")

    lines.append(f"Total projects : {len(nodes)}")
    total_sessions = sum(n.total_sessions for n in nodes.values())
    total_msgs = sum(n.total_messages for n in nodes.values())
    lines.append(f"Total sessions : {total_sessions}")
    lines.append(f"Total messages : {total_msgs}")
    return "\n".join(lines)
