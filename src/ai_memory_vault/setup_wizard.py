"""Guided onboarding for registered CLI agent integrations."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from .agents import AGENTS

console = Console()


def detect_tools() -> dict[str, dict | None]:
    """Detect registered agents from metadata owned by their adapters."""
    tools: dict[str, dict | None] = {}
    for adapter in AGENTS.select():
        data_root = adapter.native_data_root()
        tools[adapter.source] = (
            {
                "sessions": len(adapter.iter_local_native_sessions()),
                "label": adapter.label,
                "data_dir": str(data_root),
            }
            if data_root and data_root.exists()
            else None
        )
    return tools


def show_detection_panel(tools: dict) -> None:
    lines = []
    for name, info in tools.items():
        label = info["label"] if info else AGENTS.get(name).label
        if info:
            lines.append(f"  [green]available[/green] {label:<18} - {info['sessions']} sessions")
        else:
            lines.append(f"  [dim]missing   {label:<18} - not installed[/dim]")
    console.print()
    console.print(
        Panel(
            "\n".join(lines),
            title="[bold]CLI agents detected[/bold]",
            border_style="blue",
        )
    )


def run_setup_wizard() -> None:
    console.print()
    console.print(
        Panel(
            "[bold blue]Welcome to AI Memory Vault[/bold blue]\n\n"
            "This wizard discovers registered CLI agents and their local history.",
            border_style="blue",
        )
    )
    console.print("\n[bold]Scanning registered agents...[/bold]\n")
    tools = detect_tools()
    show_detection_panel(tools)

    active = {key: value for key, value in tools.items() if value is not None}
    if not active:
        console.print(
            "\n[yellow]No registered agent data found.[/yellow] "
            "Install or use a supported CLI agent, then run [bold]vault setup[/bold] again."
        )
        return

    total_sessions = sum(value["sessions"] for value in active.values())
    console.print(
        f"\nFound [bold green]{total_sessions}[/bold green] sessions across "
        f"{len(active)} registered agent(s)."
    )
    console.print("\n[dim]Run [bold]vault summary[/bold] for full statistics.[/dim]")
    console.print("[dim]Run [bold]vault tree[/bold] to inspect sessions by project.[/dim]")
    console.print(
        "[dim]Run [bold]vault push --include-raw --vault-repo <url>[/bold] "
        "to create a resumable backup.[/dim]\n"
    )
