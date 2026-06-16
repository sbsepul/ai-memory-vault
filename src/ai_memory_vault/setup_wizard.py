"""vault setup — guided onboarding wizard."""
from __future__ import annotations
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
import click

from .config import (
    CLAUDE_PROJECTS_DIR, CODEX_SESSIONS_DIR, CONFIG_DIR, CONFIG_FILE
)

console = Console()


def detect_tools() -> dict[str, dict | None]:
    """Detect installed AI tools and count their sessions."""
    tools: dict[str, dict | None] = {}

    # Claude Code
    if CLAUDE_PROJECTS_DIR.exists():
        jsonl_files = list(CLAUDE_PROJECTS_DIR.rglob("*.jsonl"))
        tools["claude"] = {
            "sessions": len(jsonl_files),
            "label": "Claude Code",
            "data_dir": str(CLAUDE_PROJECTS_DIR),
        }
    else:
        tools["claude"] = None

    # Codex CLI
    if CODEX_SESSIONS_DIR.exists():
        jsonl_files = list(CODEX_SESSIONS_DIR.rglob("*.jsonl"))
        tools["codex"] = {
            "sessions": len(jsonl_files),
            "label": "Codex CLI",
            "data_dir": str(CODEX_SESSIONS_DIR),
        }
    else:
        tools["codex"] = None

    # Future tools (not yet implemented)
    tools["cursor"] = None
    tools["windsurf"] = None

    return tools


def show_detection_panel(tools: dict) -> None:
    """Display detected AI tools in a rich panel."""
    lines = []
    for name, info in tools.items():
        label = info["label"] if info else name.capitalize()
        if info:
            lines.append(f"  [green]✅[/green] {label:<18} — {info['sessions']} sessions")
        else:
            lines.append(f"  [dim]❌ {label:<18} — not installed[/dim]")

    console.print()
    console.print(Panel(
        "\n".join(lines),
        title="[bold]AI Tools Detected[/bold]",
        border_style="blue",
    ))


def run_setup_wizard() -> None:
    """Run the interactive setup wizard."""
    console.print()
    console.print(Panel(
        "[bold blue]Welcome to AI Memory Vault[/bold blue]\n\n"
        "This wizard will help you discover your AI history\n"
        "and configure backups.",
        border_style="blue",
    ))

    console.print("\n[bold]Scanning for AI tools...[/bold]\n")
    tools = detect_tools()
    show_detection_panel(tools)

    active = {k: v for k, v in tools.items() if v is not None}
    if not active:
        console.print(
            "\n[yellow]No AI tools found.[/yellow] "
            "Install Claude Code or Codex CLI first, then run [bold]vault setup[/bold] again."
        )
        return

    total_sessions = sum(v["sessions"] for v in active.values())
    console.print(f"\nFound [bold green]{total_sessions}[/bold green] total sessions across {len(active)} tool(s).")
    console.print("\n[dim]Run [bold]vault summary[/bold] to see full statistics.[/dim]")
    console.print("[dim]Run [bold]vault tree[/bold] to see sessions by project.[/dim]")
    console.print("[dim]Run [bold]vault push --vault-repo <url>[/bold] to set up backup.[/dim]\n")
