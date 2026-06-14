"""ai-memory-vault CLI — vault <command>."""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel

from .extractors import claude as claude_ext
from .extractors import codex as codex_ext
from .exporters.markdown import export_sessions
from .tree import build_tree
from .search import search as do_search

console = Console()

DEFAULT_OUTPUT = Path.home() / "ai-memory-vault-export"

SOURCE_OPTION = click.option(
    "--source", default="all",
    type=click.Choice(["all", "claude", "codex"]),
    show_default=True,
    help="Which tool's history to include.",
)


def _load_sessions(source: str, since: str | None = None):
    sessions = []
    if source in ("claude", "all"):
        with console.status("[bold blue]Reading Claude Code sessions…"):
            sessions += claude_ext.extract_all()
    if source in ("codex", "all"):
        with console.status("[bold green]Reading Codex sessions…"):
            sessions += codex_ext.extract_all()

    if since:
        try:
            cutoff = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
            sessions = [
                s for s in sessions
                if s.updated_at and s.updated_at.replace(tzinfo=timezone.utc) >= cutoff
            ]
        except ValueError:
            console.print(f"[yellow]Warning: invalid --since date '{since}', ignored.[/yellow]")

    return sessions


@click.group()
@click.version_option()
def main():
    """Unified export and search for Claude Code and Codex CLI conversation history."""


# ── summary ──────────────────────────────────────────────────────────────────

@main.command("summary")
@SOURCE_OPTION
def cmd_summary(source: str):
    """Print total sessions, messages, and projects per source."""
    sessions = _load_sessions(source)
    claude_s = [s for s in sessions if s.source == "claude"]
    codex_s = [s for s in sessions if s.source == "codex"]

    table = Table(title="AI Memory Vault — Summary", show_footer=False)
    table.add_column("Source", style="bold")
    table.add_column("Sessions", justify="right")
    table.add_column("Messages", justify="right")
    table.add_column("Projects", justify="right")

    def _row(lst, label, style):
        projects = len({s.project_rel_path for s in lst})
        msgs = sum(s.message_count for s in lst)
        table.add_row(f"[{style}]{label}[/{style}]", str(len(lst)), str(msgs), str(projects))

    if claude_s:
        _row(claude_s, "Claude Code", "blue")
    if codex_s:
        _row(codex_s, "Codex", "green")

    total_msgs = sum(s.message_count for s in sessions)
    total_projs = len({s.project_rel_path for s in sessions})
    table.add_row("[bold]Total[/bold]", f"[bold]{len(sessions)}[/bold]",
                  f"[bold]{total_msgs}[/bold]", f"[bold]{total_projs}[/bold]")

    console.print(table)


# ── tree ──────────────────────────────────────────────────────────────────────

@main.command("tree")
@SOURCE_OPTION
def cmd_tree(source: str):
    """Show a tree of all projects that have AI conversation history."""
    sessions = _load_sessions(source)
    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        return

    nodes = build_tree(sessions)

    table = Table(title="AI Memory Vault — Project Tree", show_lines=True)
    table.add_column("Project (rel. to ~)", style="cyan", no_wrap=False)
    table.add_column("Git", justify="center")
    table.add_column("Claude", justify="right")
    table.add_column("Codex", justify="right")
    table.add_column("Msgs", justify="right")

    for path, node in nodes.items():
        git_icon = ":white_check_mark:" if node.has_git else ":x:"
        claude_str = f"{node.claude_sessions}s / {node.claude_messages}m" if node.claude_sessions else "-"
        codex_str = f"{node.codex_sessions}s / {node.codex_messages}m" if node.codex_sessions else "-"
        table.add_row(path, git_icon, claude_str, codex_str, str(node.total_messages))

    console.print(table)
    total_sessions = sum(n.total_sessions for n in nodes.values())
    console.print(
        f"\n[bold]{len(nodes)} projects[/bold] · "
        f"[bold]{total_sessions} sessions[/bold]"
    )


# ── ls ────────────────────────────────────────────────────────────────────────

@main.command("ls")
@SOURCE_OPTION
@click.option("--project", "-p", default=None, help="Filter by project path (partial match).")
@click.option("--limit", "-n", default=50, show_default=True, help="Max sessions to show.")
def cmd_ls(source: str, project: str | None, limit: int):
    """List sessions for a project, newest first."""
    sessions = _load_sessions(source)

    if project:
        sessions = [s for s in sessions if project.lower() in s.project_rel_path.lower()]

    sessions.sort(key=lambda s: s.updated_at or datetime.min, reverse=True)
    sessions = sessions[:limit]

    if not sessions:
        console.print("[yellow]No sessions matched.[/yellow]")
        return

    table = Table(show_lines=False)
    table.add_column("Updated", style="dim", no_wrap=True)
    table.add_column("Source", justify="center")
    table.add_column("Project", style="cyan")
    table.add_column("Name / Thread")
    table.add_column("Msgs", justify="right")

    for s in sessions:
        ts = s.updated_at.strftime("%Y-%m-%d %H:%M") if s.updated_at else "?"
        src_color = "blue" if s.source == "claude" else "green"
        table.add_row(
            ts,
            f"[{src_color}]{s.source}[/{src_color}]",
            s.project_rel_path,
            s.name,
            str(s.message_count),
        )

    console.print(table)


# ── search ────────────────────────────────────────────────────────────────────

@main.command("search")
@click.argument("query")
@SOURCE_OPTION
@click.option("--project", "-p", default=None, help="Restrict to a project (partial match).")
@click.option("--limit", "-n", default=20, show_default=True, help="Max results.")
@click.option("--case-sensitive", is_flag=True, default=False)
def cmd_search(query: str, source: str, project: str | None, limit: int, case_sensitive: bool):
    """Search all conversation history for QUERY."""
    sessions = _load_sessions(source)

    if project:
        sessions = [s for s in sessions if project.lower() in s.project_rel_path.lower()]

    hits = do_search(sessions, query, case_sensitive=case_sensitive)

    if not hits:
        console.print(f"[yellow]No results for '{query}'.[/yellow]")
        return

    hits = hits[:limit]
    console.print(f"[bold]{len(hits)} results[/bold] for [bold cyan]'{query}'[/bold cyan]\n")

    for hit in hits:
        s = hit.session
        ts = hit.message.timestamp.strftime("%Y-%m-%d") if hit.message.timestamp else "?"
        src_color = "blue" if s.source == "claude" else "green"
        role_color = "yellow" if hit.message.role == "user" else "white"

        header = (
            f"[{src_color}]{s.source}[/{src_color}]  "
            f"[cyan]{s.project_rel_path}[/cyan]  "
            f"[dim]{ts}[/dim]  "
            f"[{role_color}]{hit.message.role}[/{role_color}]"
        )
        # Highlight the query in the snippet
        highlighted = hit.snippet.replace(
            query, f"[bold yellow]{query}[/bold yellow]"
        ) if not case_sensitive else hit.snippet.replace(
            query, f"[bold yellow]{query}[/bold yellow]"
        )
        console.print(Panel(highlighted, title=header, title_align="left", padding=(0, 1)))


# ── export ────────────────────────────────────────────────────────────────────

@main.command("export")
@SOURCE_OPTION
@click.option("--output", "-o", default=str(DEFAULT_OUTPUT), show_default=True,
              type=click.Path(), help="Output directory.")
@click.option("--project", "-p", default=None, help="Filter by project path (partial match).")
@click.option("--format", "fmt", default="markdown",
              type=click.Choice(["markdown", "json"]), show_default=True)
@click.option("--since", default=None, metavar="DATE",
              help="Only export sessions updated after DATE (ISO format, e.g. 2026-01-01).")
def cmd_export(source: str, output: str, project: str | None, fmt: str, since: str | None):
    """Export conversation history to Markdown or JSON files."""
    sessions = _load_sessions(source, since=since)

    if project:
        sessions = [s for s in sessions if project.lower() in s.project_rel_path.lower()]

    if not sessions:
        console.print("[yellow]No sessions matched.[/yellow]")
        return

    output_path = Path(output)

    if fmt == "markdown":
        written = export_sessions(sessions, output_path)
        console.print(
            f"[green]✓ Exported {len(written)} sessions[/green] → [cyan]{output_path}[/cyan]"
        )
    elif fmt == "json":
        output_path.mkdir(parents=True, exist_ok=True)
        out_file = output_path / "sessions.json"
        data = [
            {
                "id": s.id,
                "source": s.source,
                "project_rel_path": s.project_rel_path,
                "name": s.name,
                "has_git": s.has_git,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                    }
                    for m in s.messages
                ],
            }
            for s in sessions
        ]
        out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(
            f"[green]✓ Exported {len(sessions)} sessions[/green] → [cyan]{out_file}[/cyan]"
        )


# ── push ─────────────────────────────────────────────────────────────────────

@main.command("push")
@SOURCE_OPTION
@click.option("--vault-repo", default=None, metavar="URL",
              help="Private git repo URL (saved after first use).")
@click.option("--output", "-o", default=str(DEFAULT_OUTPUT), show_default=True,
              type=click.Path(), help="Local export directory to commit.")
@click.option("--since", default=None, metavar="DATE",
              help="Only export sessions updated after DATE before pushing.")
@click.option("--include-raw", is_flag=True, default=False,
              help="Also backup raw Claude JSONL files (enables full restore on another machine).")
def cmd_push(source: str, vault_repo: str | None, output: str, since: str | None, include_raw: bool):
    """Export sessions and push them to a private git repository."""
    from .sync.git import push_to_vault

    sessions = _load_sessions(source, since=since)
    if not sessions:
        console.print("[yellow]No sessions to push.[/yellow]")
        return

    output_path = Path(output)
    with console.status("Exporting sessions…"):
        export_sessions(sessions, output_path)

    with console.status("Pushing to vault repo…"):
        try:
            msg = push_to_vault(output_path, vault_repo, include_raw=include_raw)
            if msg == "nothing to commit":
                console.print("[yellow]Nothing new to push — vault is already up to date.[/yellow]")
            else:
                console.print(f"[green]✓ Pushed:[/green] {msg}")
                if include_raw:
                    console.print(
                        "[dim]Raw Claude JSONL files included — "
                        "use [bold]vault pull --restore-claude[/bold] on the new machine.[/dim]"
                    )
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(1)


# ── pull ─────────────────────────────────────────────────────────────────────

@main.command("pull")
@click.option("--vault-repo", default=None, metavar="URL",
              help="Private git repo URL (saved after first use).")
@click.option("--output", "-o", default=str(DEFAULT_OUTPUT), show_default=True,
              type=click.Path(), help="Where to place the downloaded export files.")
@click.option("--restore-claude", is_flag=True, default=False,
              help=(
                  "Restore raw Claude JSONL files to ~/.claude/projects/, "
                  "re-encoding paths for this machine. "
                  "Requires a prior push with --include-raw."
              ))
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would be restored without writing anything.")
def cmd_pull(vault_repo: str | None, output: str, restore_claude: bool, dry_run: bool):
    """Pull conversation history from the vault repo to this machine.

    \b
    Two modes:
      Default          — downloads Markdown exports for browsing (always works).
      --restore-claude — also restores Claude Code sessions so Claude can load
                         them natively. Requires a prior push with --include-raw.

    \b
    Path remapping is automatic: sessions pushed from /home/alice/repos/project
    are restored to /home/bob/repos/project on the new machine, because vault
    stores only the relative path (repos/project).
    """
    from .sync.git import pull_from_vault
    from rich.table import Table

    output_path = Path(output)

    with console.status("Pulling from vault repo…"):
        try:
            result = pull_from_vault(
                vault_repo,
                output_path,
                restore_claude=restore_claude,
                dry_run=dry_run,
            )
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(1)

    prefix = "[dim][dry-run][/dim] " if dry_run else ""

    # ── exports ───────────────────────────────────────────────────────────────
    if result.export_files:
        console.print(
            f"{prefix}[green]✓ {result.export_files} Markdown files[/green] "
            f"→ [cyan]{output_path}[/cyan]"
        )
    elif not dry_run:
        console.print(
            "[yellow]No Markdown exports found in vault "
            "(run vault push first).[/yellow]"
        )

    # ── claude restore ────────────────────────────────────────────────────────
    if restore_claude:
        if not result.restored_sessions:
            console.print(
                "[yellow]No raw Claude sessions found in vault. "
                "Re-run push with --include-raw first.[/yellow]"
            )
        else:
            home = Path.home()
            claude_projects = home / ".claude" / "projects"

            table = Table(
                title=f"{'[dry-run] ' if dry_run else ''}Claude sessions restored",
                show_lines=False,
            )
            table.add_column("Project (rel. to ~)", style="cyan")
            table.add_column("→ ~/.claude/projects/ slug", style="dim")

            seen_paths: set[str] = set()
            for rel_path, slug in result.restored_sessions:
                if rel_path not in seen_paths:
                    table.add_row(rel_path, slug)
                    seen_paths.add(rel_path)

            console.print(table)

            if not dry_run:
                console.print(
                    f"\n{prefix}[green]✓ {len(result.restored_sessions)} session files[/green] "
                    f"restored to [cyan]{claude_projects}[/cyan]\n"
                    "[dim]Restart Claude Code to pick up the restored sessions.[/dim]"
                )
