"""Registration and alias resolution for CLI agent integrations."""

from __future__ import annotations

from collections.abc import Iterable

from .base import AgentAdapter
from .claude import ClaudeAgentAdapter
from .codex import CodexAgentAdapter


class AgentRegistry:
    def __init__(self, adapters: Iterable[AgentAdapter] = ()) -> None:
        self._adapters: dict[str, AgentAdapter] = {}
        self._aliases: dict[str, str] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: AgentAdapter) -> None:
        if adapter.source in self._adapters:
            raise ValueError(f"Agent source already registered: {adapter.source}")
        self._adapters[adapter.source] = adapter
        for name in (adapter.source, *adapter.aliases):
            normalized = name.strip().lower()
            if normalized in self._aliases:
                raise ValueError(f"Agent name already registered: {name}")
            self._aliases[normalized] = adapter.source

    def get(self, name: str) -> AgentAdapter:
        canonical = self._aliases.get(name.strip().lower(), name.strip().lower())
        try:
            return self._adapters[canonical]
        except KeyError as error:
            raise ValueError(f"Unsupported agent: {name}") from error

    def select(self, names: Iterable[str] | None = None) -> list[AgentAdapter]:
        requested = list(names or ())
        if not requested or "all" in requested:
            return list(self._adapters.values())
        selected: dict[str, AgentAdapter] = {}
        for name in requested:
            adapter = self.get(name)
            selected[adapter.source] = adapter
        return list(selected.values())

    def canonical_source(self, name: str) -> str:
        return self.get(name).source

    def choices(self, include_all: bool = True) -> list[str]:
        choices = sorted(self._aliases)
        return ["all", *choices] if include_all else choices

    def color(self, source: str) -> str:
        try:
            return self.get(source).color
        except ValueError:
            return "white"


AGENTS = AgentRegistry([ClaudeAgentAdapter(), CodexAgentAdapter()])
