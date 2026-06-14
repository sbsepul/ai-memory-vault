"""Click-based CLI interface for AI Memory Vault."""

from __future__ import annotations

import json
import shutil
import subprocess as sp
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..application.export_service import sessions_to_json_ready
from ..application.session_loader import SessionLoader
from ..config import (
    DEFAULT_LS_LIMIT,
    DEFAULT_MEMORIES_LIMIT,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SEARCH_DEPTH,
    DEFAULT_SEARCH_LIMIT,
    SOURCE_COLORS,
)
from ..domain.project_tree import build_tree
from ..infrastructure.exporters.markdown import export_sessions
from ..infrastructure.extractors.codex_memory import extract_memories as extract_codex_memories
from ..resolver import load_path_map, resolve_orphans, save_path_map
from ..search import search as do_search
from ..status import build_status
from ..sync.git import pull_from_vault, push_to_vault
from ..utils import fmt_ts

console = Console()
loader = SessionLoader(console=console)

SOURCE_OPTION = click.option(
    "--source",
    default="all",
    type=click.Choice(["all", "claude", "codex"]),
    show_default=True,
    help="Which tool's history to include.",
)


@click.group()
@click.version_option()
def main() -> None:
    """Unified export and search for Claude Code and Codex CLI conversation history."""


@main.command("summary")
@SOURCE_OPTION
def cmd_summary(source: str) -> None:
    sessions = loader.load(source)
    claude_sessions = [session for session in sessions if session.source == "claude"]
    codex_sessions = [session for session in sessions if session.source == "codex"]

    table = Table(title="AI Memory Vault — Summary", show_footer=False)
    table.add_column("Source", style="bold")
    table.add_column("Sessions", justify="right")
    table.add_column("Messages", justify="right")
    table.add_column("Projects", justify="right")

    def add_row(items: list, label: str, style: str) -> None:
        projects = len({session.project_rel_path for session in items})
        messages = sum(session.message_count for session in items)
        table.add_row(f"[{style}]{label}[/{style}]", str(len(items)), str(messages), str(projects))

    if claude_sessions:
        add_row(claude_sessions, "Claude Code", "blue")
    if codex_sessions:
        add_row(codex_sessions, "Codex", "green")

    total_messages = sum(session.message_count for session in sessions)
    total_projects = len({session.project_rel_path for session in sessions})
    table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{len(sessions)}[/bold]",
        f"[bold]{total_messages}[/bold]",
        f"[bold]{total_projects}[/bold]",
    )
    console.print(table)


@main.command("tree")
@SOURCE_OPTION
def cmd_tree(source: str) -> None:
    sessions = loader.load(source)
    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        return

    nodes = build_tree(sessions)
    table = Table(title="AI Memory Vault — Project Tree", show_lines=True)
    table.add_column("Project (rel. to ~)", style="cyan")
    table.add_column("Git", justify="center")
    table.add_column("Claude", justify="right")
    table.add_column("Codex", justify="right")
    table.add_column("Msgs", justify="right")

    all_paths = set(nodes.keys())
    for path, node in nodes.items():
        is_parent = any(candidate.startswith(path + "/") for candidate in all_paths)
        if node.has_git:
            git_icon = ":white_check_mark:"
        elif node.path_exists and not is_parent:
            git_icon = ":open_file_folder:"
        elif node.path_exists:
            git_icon = ":card_index_dividers:"
        else:
            git_icon = ":x:"
        claude = (
            f"{node.claude_sessions}s / {node.claude_messages}m" if node.claude_sessions else "-"
        )
        codex = f"{node.codex_sessions}s / {node.codex_messages}m" if node.codex_sessions else "-"
        table.add_row(path, git_icon, claude, codex, str(node.total_messages))

    console.print(table)
    total_sessions = sum(node.total_sessions for node in nodes.values())
    console.print(f"\n[bold]{len(nodes)} projects[/bold] · [bold]{total_sessions} sessions[/bold]")


@main.command("ls")
@SOURCE_OPTION
@click.option("--project", "-p", default=None, help="Filter by project path (partial match).")
@click.option(
    "--limit",
    "-n",
    default=DEFAULT_LS_LIMIT,
    show_default=True,
    help="Max sessions to show.",
)
def cmd_ls(source: str, project: str | None, limit: int) -> None:
    sessions = loader.filter_by_project(loader.load(source), project)
    sessions.sort(key=lambda session: session.updated_at or datetime.min, reverse=True)
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

    for session in sessions:
        color = SOURCE_COLORS.get(session.source, "white")
        table.add_row(
            fmt_ts(session.updated_at),
            f"[{color}]{session.source}[/{color}]",
            session.project_rel_path,
            session.name,
            str(session.message_count),
        )

    console.print(table)


@main.command("search")
@click.argument("query")
@SOURCE_OPTION
@click.option("--project", "-p", default=None, help="Restrict to a project (partial match).")
@click.option(
    "--limit",
    "-n",
    default=DEFAULT_SEARCH_LIMIT,
    show_default=True,
    help="Max results.",
)
@click.option("--case-sensitive", is_flag=True, default=False)
def cmd_search(
    query: str,
    source: str,
    project: str | None,
    limit: int,
    case_sensitive: bool,
) -> None:
    sessions = loader.filter_by_project(loader.load(source), project)
    hits = do_search(sessions, query, case_sensitive=case_sensitive)

    if not hits:
        console.print(f"[yellow]No results for '{query}'.[/yellow]")
        return

    console.print(
        f"[bold]{len(hits[:limit])} results[/bold] for [bold cyan]'{query}'[/bold cyan]\n"
    )
    for hit in hits[:limit]:
        session = hit.session
        ts = fmt_ts(hit.message.timestamp, "%Y-%m-%d")
        src_color = SOURCE_COLORS.get(session.source, "white")
        role_color = "yellow" if hit.message.role == "user" else "white"
        header = (
            f"[{src_color}]{session.source}[/{src_color}]  "
            f"[cyan]{session.project_rel_path}[/cyan]  "
            f"[dim]{ts}[/dim]  "
            f"[{role_color}]{hit.message.role}[/{role_color}]"
        )
        highlighted = hit.snippet.replace(query, f"[bold yellow]{query}[/bold yellow]")
        console.print(Panel(highlighted, title=header, title_align="left", padding=(0, 1)))


@main.command("export")
@SOURCE_OPTION
@click.option(
    "--output",
    "-o",
    default=str(DEFAULT_OUTPUT_DIR),
    show_default=True,
    type=click.Path(),
    help="Output directory.",
)
@click.option("--project", "-p", default=None, help="Filter by project path (partial match).")
@click.option(
    "--format",
    "fmt",
    default="markdown",
    type=click.Choice(["markdown", "json"]),
    show_default=True,
)
@click.option(
    "--since",
    default=None,
    metavar="DATE",
    help="Only export sessions updated after DATE (ISO format, e.g. 2026-01-01).",
)
def cmd_export(source: str, output: str, project: str | None, fmt: str, since: str | None) -> None:
    sessions = loader.filter_by_project(loader.load(source, since=since), project)
    if not sessions:
        console.print("[yellow]No sessions matched.[/yellow]")
        return

    output_path = Path(output)
    if fmt == "markdown":
        written = export_sessions(sessions, output_path)
        console.print(
            f"[green]✓ Exported {len(written)} sessions[/green] → [cyan]{output_path}[/cyan]"
        )
        return

    output_path.mkdir(parents=True, exist_ok=True)
    out_file = output_path / "sessions.json"
    out_file.write_text(
        json.dumps(sessions_to_json_ready(sessions), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    console.print(f"[green]✓ Exported {len(sessions)} sessions[/green] → [cyan]{out_file}[/cyan]")


@main.command("push")
@SOURCE_OPTION
@click.option(
    "--vault-repo",
    default=None,
    metavar="URL",
    help="Private git repo URL (saved after first use).",
)
@click.option(
    "--output",
    "-o",
    default=str(DEFAULT_OUTPUT_DIR),
    show_default=True,
    type=click.Path(),
    help="Local export directory to commit.",
)
@click.option(
    "--since",
    default=None,
    metavar="DATE",
    help="Only export sessions updated after DATE before pushing.",
)
@click.option(
    "--include-raw",
    is_flag=True,
    default=False,
    help="Also backup raw Claude JSONL files.",
)
def cmd_push(
    source: str,
    vault_repo: str | None,
    output: str,
    since: str | None,
    include_raw: bool,
) -> None:
    sessions = loader.load(source, since=since)
    if not sessions:
        console.print("[yellow]No sessions to push.[/yellow]")
        return

    output_path = Path(output)
    with console.status("Exporting sessions…"):
        export_sessions(sessions, output_path)

    with console.status("Pushing to vault repo…"):
        try:
            message = push_to_vault(output_path, vault_repo, include_raw=include_raw)
        except ValueError as error:
            console.print(f"[red]{error}[/red]")
            raise SystemExit(1) from error

    if message == "nothing to commit":
        console.print("[yellow]Nothing new to push — vault is already up to date.[/yellow]")
        return

    console.print(f"[green]✓ Pushed:[/green] {message}")
    if include_raw:
        console.print(
            "[dim]Raw Claude JSONL files included — use "
            "[bold]vault pull --restore-claude[/bold] on the new machine.[/dim]"
        )


@main.command("pull")
@click.option(
    "--vault-repo",
    default=None,
    metavar="URL",
    help="Private git repo URL (saved after first use).",
)
@click.option(
    "--output",
    "-o",
    default=str(DEFAULT_OUTPUT_DIR),
    show_default=True,
    type=click.Path(),
    help="Where to place the downloaded export files.",
)
@click.option(
    "--restore-claude",
    is_flag=True,
    default=False,
    help="Restore raw Claude JSONL files to ~/.claude/projects/.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be restored without writing anything.",
)
def cmd_pull(vault_repo: str | None, output: str, restore_claude: bool, dry_run: bool) -> None:
    output_path = Path(output)
    with console.status("Pulling from vault repo…"):
        try:
            result = pull_from_vault(
                vault_repo,
                output_path,
                restore_claude=restore_claude,
                dry_run=dry_run,
            )
        except ValueError as error:
            console.print(f"[red]{error}[/red]")
            raise SystemExit(1) from error

    prefix = "[dim][dry-run][/dim] " if dry_run else ""
    if result.export_files:
        console.print(
            f"{prefix}[green]✓ {result.export_files} Markdown files[/green] "
            f"→ [cyan]{output_path}[/cyan]"
        )
    elif not dry_run:
        console.print("[yellow]No Markdown exports found in vault (run vault push first).[/yellow]")

    if restore_claude:
        if not result.restored_sessions:
            console.print(
                "[yellow]No raw Claude sessions found in vault. "
                "Re-run push with --include-raw first.[/yellow]"
            )
            return

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
                f"restored to [cyan]{Path.home() / '.claude' / 'projects'}[/cyan]"
            )


@main.command("memories")
@click.option("--project", "-p", default=None, help="Filter by project path (partial match).")
@click.option(
    "--output",
    "-o",
    default=None,
    type=click.Path(),
    help="Export memories to a Markdown file instead of printing.",
)
@click.option("--limit", "-n", default=DEFAULT_MEMORIES_LIMIT, show_default=True)
def cmd_memories(project: str | None, output: str | None, limit: int) -> None:
    with console.status("[bold green]Reading Codex memories…"):
        memories = extract_codex_memories()

    if project:
        memories = [
            memory for memory in memories if project.lower() in memory.project_rel_path.lower()
        ]
    memories = memories[:limit]

    if not memories:
        console.print("[yellow]No Codex memories found.[/yellow]")
        return

    if output:
        lines = [f"# Codex Memories\n\nTotal: {len(memories)}\n\n---\n"]
        for memory in memories:
            ts = memory.generated_at.strftime("%Y-%m-%d %H:%M UTC") if memory.generated_at else "?"
            lines.append(f"## {memory.thread_title or memory.thread_id[:8]}")
            lines.append(f"- **Project**: `{memory.project_rel_path}`")
            lines.append(f"- **Generated**: {ts}  |  **Used**: {memory.usage_count}x\n")
            if memory.rollout_summary:
                lines.append(f"**Summary**\n\n{memory.rollout_summary}\n")
            if memory.raw_memory:
                lines.append(f"**Full memory**\n\n{memory.raw_memory}\n")
            lines.append("---\n")
        Path(output).write_text("\n".join(lines), encoding="utf-8")
        console.print(f"[green]✓ {len(memories)} memories exported[/green] → [cyan]{output}[/cyan]")
        return

    console.print(f"[bold]{len(memories)} Codex memory summaries[/bold]\n")
    for memory in memories:
        ts = memory.generated_at.strftime("%Y-%m-%d") if memory.generated_at else "?"
        header = (
            f"[green]{memory.project_rel_path}[/green]  "
            f"[dim]{ts}  used {memory.usage_count}x[/dim]  "
            f"[bold]{memory.thread_title or memory.thread_id[:8]}[/bold]"
        )
        body = (memory.rollout_summary or memory.raw_memory or "")[:400]
        if len(memory.rollout_summary or memory.raw_memory or "") > 400:
            body += "…"
        console.print(Panel(body, title=header, title_align="left", padding=(0, 1)))


@main.command("status")
@SOURCE_OPTION
@click.option(
    "--search-dir",
    "-d",
    multiple=True,
    type=click.Path(),
    help="Extra directories to scan for git repos.",
)
@click.option(
    "--depth",
    default=DEFAULT_SEARCH_DEPTH,
    show_default=True,
    help="Max directory depth when scanning for git repos.",
)
@click.option(
    "--resolve",
    is_flag=True,
    default=False,
    help="Auto-detect orphan→canonical path mappings and save them.",
)
def cmd_status(source: str, search_dir: tuple, depth: int, resolve: bool) -> None:
    sessions = loader.load(source)
    dirs = [Path(path) for path in search_dir] if search_dir else None

    with console.status("Scanning git repos on disk…"):
        report = build_status(sessions, search_dirs=dirs, max_depth=depth)

    if resolve and report.orphan:
        with console.status("[yellow]Resolving orphan paths…"):
            new_matches = resolve_orphans(report.orphan, report.disk_repos)
        merged = {**load_path_map(), **new_matches}
        if new_matches:
            table = Table(title="Path mappings resolved", show_lines=False)
            table.add_column("Orphan path (old)", style="yellow")
            table.add_column("→ Canonical path (current)", style="green")
            for old, new in sorted(new_matches.items()):
                table.add_row(old, new)
            console.print(table)
            save_path_map(merged)
            console.print(
                "\n[green]✓ Mappings saved[/green] → "
                "[dim]~/.config/ai-memory-vault/path-map.json[/dim]"
            )
            sessions = loader.load(source)
            report = build_status(sessions, search_dirs=dirs, max_depth=depth)
        else:
            console.print("[yellow]No new mappings found automatically.[/yellow]")

    exists_no_git = report.orphan_exists_no_git
    missing = report.orphan_missing

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column(justify="right", style="bold")
    summary.add_row("Git repos on disk", str(len(report.disk_repos)))
    summary.add_row("Projects with AI history", str(len(report.ai_paths)))
    summary.add_row(
        "[green]✅ repo + history[/green]",
        f"[green]{len(report.with_history)}[/green]",
    )
    summary.add_row("[red]❌ repo, no history[/red]", f"[red]{len(report.no_history)}[/red]")
    summary.add_row("[cyan]📂 files, no git[/cyan]", f"[cyan]{len(exists_no_git)}[/cyan]")
    summary.add_row("[yellow]👻 history, dir gone[/yellow]", f"[yellow]{len(missing)}[/yellow]")
    console.print()
    console.print(Panel(summary, title="vault status", padding=(0, 2)))

    if report.with_history:
        table = Table(
            title=f"✅ Repos with AI history ({len(report.with_history)})",
            show_lines=False,
        )
        table.add_column("Project (rel. to ~)", style="cyan")
        table.add_column("Sessions", justify="right")
        table.add_column("Messages", justify="right")
        for path, (n_sessions, n_messages) in sorted(report.with_history_stats(sessions).items()):
            table.add_row(path, str(n_sessions), str(n_messages))
        console.print(table)

    if report.no_history:
        table = Table(
            title=f"❌ Repos with NO AI history ({len(report.no_history)})",
            show_lines=False,
        )
        table.add_column("Project (rel. to ~)", style="dim")
        for path in sorted(report.no_history):
            table.add_row(path)
        console.print(table)

    if exists_no_git:
        table = Table(
            title=f"📂 Dirs with AI history but no git repo ({len(exists_no_git)})",
            show_lines=False,
        )
        table.add_column("Path (rel. to ~)", style="cyan")
        table.add_column("Sessions", justify="right")
        table.add_column("Messages", justify="right")
        stats = report.orphan_stats(sessions)
        for path in sorted(exists_no_git):
            n_sessions, n_messages = stats.get(path, (0, 0))
            table.add_row(path, str(n_sessions), str(n_messages))
        console.print(table)

    if missing:
        table = Table(
            title=f"👻 AI history whose directory no longer exists ({len(missing)})",
            show_lines=False,
        )
        table.add_column("Path (rel. to ~)", style="yellow")
        table.add_column("Sessions", justify="right")
        table.add_column("Messages", justify="right")
        table.add_column("Note", style="dim")
        stats = report.orphan_stats(sessions)
        for path in sorted(missing):
            n_sessions, n_messages = stats.get(path, (0, 0))
            table.add_row(path, str(n_sessions), str(n_messages), "dir moved/renamed?")
        console.print(table)


@main.command("init")
@click.option("--project", "-p", required=True, help="Project path relative to ~.")
@click.option(
    "--remote/--no-remote",
    default=True,
    show_default=True,
    help="Create a GitHub repository with 'gh repo create'.",
)
@click.option("--private/--public", default=True, show_default=True, help="GitHub repo visibility.")
def cmd_init(project: str, remote: bool, private: bool) -> None:
    project_path = Path.home() / project
    if not project_path.exists():
        console.print(f"[red]Directory not found:[/red] ~/{project}")
        raise SystemExit(1)
    if (project_path / ".git").exists():
        console.print(f"[yellow]Already a git repo:[/yellow] ~/{project}")
        raise SystemExit(0)

    def run(cmd: list[str], **kwargs) -> sp.CompletedProcess:
        return sp.run(cmd, cwd=project_path, check=True, **kwargs)

    console.print(f"\n[bold]Initializing git repo in[/bold] ~/{project}\n")
    run(["git", "init", "-b", "main"])
    run(["git", "add", "-A"])

    status = sp.run(["git", "status", "--short"], cwd=project_path, capture_output=True, text=True)
    if status.stdout.strip():
        run(["git", "commit", "-m", "initial commit"])
        console.print("[green]✓ Initial commit created[/green]")
    else:
        console.print("[yellow]No files to commit (empty directory)[/yellow]")

    if not remote:
        console.print(f"\n[green]Done.[/green] Git repo initialized at ~/{project}")
        return

    if not shutil.which("gh"):
        console.print(
            "\n[yellow]'gh' CLI not found — skipping GitHub repo creation.[/yellow]\n"
            f"To push manually:\n"
            f"  gh repo create --source ~/{project} --push\n"
            f"  git -C ~/{project} push -u origin main"
        )
        return

    repo_name = project_path.name
    visibility = "--private" if private else "--public"
    console.print(f"\nCreating GitHub repo [bold]{repo_name}[/bold] ({visibility[2:]})…")
    try:
        run(["gh", "repo", "create", repo_name, visibility, "--source", ".", "--push"])
        console.print(f"[green]✓ Pushed to GitHub:[/green] {repo_name}")
    except sp.CalledProcessError:
        console.print(
            f"\n[red]GitHub repo creation failed.[/red] "
            f"Try manually:\n  gh repo create {repo_name} {visibility} --source . --push"
        )
