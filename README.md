# ai-memory-vault

> Unified export, search, and sync for **Claude Code CLI** and **Codex CLI** conversation history.

Your AI sessions accumulate locally but disappear when you switch machines. `ai-memory-vault` extracts every conversation from both tools, normalizes paths relative to `$HOME` (so they survive machine migrations), and lets you explore, search, and export everything in one command.

```
vault summary
```
```
           AI Memory Vault — Summary
┏━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ Source      ┃ Sessions ┃ Messages ┃ Projects ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ Claude Code │       65 │    20541 │       12 │
│ Codex       │      763 │    49642 │       75 │
│ Total       │      828 │    70183 │       85 │
└─────────────┴──────────┴──────────┴──────────┘
```

## Features

- **Dual-source extraction** — reads `~/.claude/projects/` (JSONL) and `~/.codex/sessions/` (JSONL + SQLite index) without any configuration
- **Portable paths** — strips `$HOME` prefix so `work/my-project` works on any machine, regardless of username or OS
- **Project tree** — see which directories have AI history, whether they have a git repo or not
- **Full-text search** — grep across 70 000+ messages in milliseconds
- **Codex memory summaries** — surfaces the condensed notes Codex silently generates per session in SQLite (`memories_1.sqlite`), invisible from the normal UI
- **Multiple export formats** — Markdown (human-readable) or JSON (for scripts)
- **Private vault sync** — push exports to any private git repo for backup and cross-machine access

## Why this exists

| Problem | Solution |
|---|---|
| Claude Code history lives in `~/.claude/` (not backed up) | `vault export` → portable Markdown / JSON |
| Codex history lives in `~/.codex/` (no export tool existed) | Built from scratch, handles all Codex event types |
| Codex memory summaries buried in SQLite, invisible to users | `vault memories` extracts them from `memories_1.sqlite` |
| Paths are absolute → break on new machine | All paths stored relative to `$HOME` |
| No way to search old conversations | `vault search <query>` across all sources |
| Can't see which projects have history | `vault tree` with git status per directory |

## Installation

```bash
git clone https://github.com/sbsepul/ai-memory-vault.git
cd ai-memory-vault
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

**Requirements**: Python 3.10+, Claude Code CLI and/or Codex CLI installed locally.

## Commands

### `vault summary`
Quick count of sessions, messages, and projects per tool.

```bash
vault summary
vault summary --source claude
vault summary --source codex
```

### `vault tree`
Project tree showing every directory that has AI conversation history, with git status.

```bash
vault tree
vault tree --source codex
```

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Project (rel. to ~)        ┃ Git ┃ Claude      ┃ Codex        ┃ Total msgs ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ repos/dream-home           │ ✅  │ 9s / 2383m  │ 16s / 2190m  │       4573 │
│ work/my-company/backend    │ ✅  │ 12s / 4210m │ 87s / 9841m  │      14051 │
│ Downloads/analysis         │ ❌  │ -           │ 7s / 51m     │         51 │
└────────────────────────────┴─────┴─────────────┴──────────────┴────────────┘
```

The `❌` (no-git) rows are exactly the ones you can't recover from version control — those are the most important to back up.

### `vault ls`
List sessions for a specific project.

```bash
vault ls --project dream-home
vault ls --project my-company --source codex --limit 20
```

### `vault search`
Full-text search across all sessions.

```bash
vault search "authentication middleware"
vault search "docker compose" --source codex
vault search "migration" --project my-company --limit 5
```

### `vault export`
Export sessions to Markdown or JSON.

```bash
vault export                                    # everything → ~/ai-memory-vault-export/
vault export --source codex                     # only Codex
vault export --project dream-home               # filter by project (partial match)
vault export --format json --output ./backup    # JSON for scripts
vault export --since 2026-01-01                 # only recent sessions
```

Output structure mirrors `source/project_rel_path/`:
```
~/ai-memory-vault-export/
├── claude/
│   └── repos/dream-home/
│       ├── 20260115-1430_37825382.md
│       └── 20260203-0912_54da0e24.md
└── codex/
    └── work/my-company/backend/
        └── 20260601-1219_019e83fc.md
```

### `vault push`
Export and commit to a private git repository.

```bash
# First time: set the private vault repo URL (saved for future runs)
vault push --vault-repo git@github.com:youruser/my-private-vault.git

# Subsequent pushes
vault push

# Also backup raw Claude JSONL files so the new machine can fully restore them
vault push --include-raw
```

### `vault memories`
Show the condensed memory summaries that Codex auto-generates after each session
and stores silently in `~/.codex/memories_1.sqlite` — not visible anywhere in the UI.

```bash
vault memories                              # all summaries, newest first
vault memories --project dream-home         # filter by project
vault memories --output codex-memories.md  # export to Markdown file
vault memories --limit 10
```

```
80 Codex memory summaries

╭─ repos/dream-home  2026-05-14  used 3x  scraping pipeline ─────────────────╮
│ # Property scraping pipeline for dream-home                                 │
│ The user set up a Playwright-based scraper targeting Portal Inmobiliario.   │
│ Key decisions: rotating user-agents, exponential backoff on 429s,           │
│ storing raw HTML before parsing so reruns don't need re-fetching…           │
╰─────────────────────────────────────────────────────────────────────────────╯
```

> These summaries are the most condensed, high-signal notes about your past
> work. Codex generates them automatically — `vault memories` is the only way
> to read them outside the Codex UI.

### `vault pull`
Pull conversation history from the vault repo to this machine.

```bash
# Download Markdown exports for browsing (always works)
vault pull --vault-repo git@github.com:youruser/my-private-vault.git

# Also restore Claude Code sessions natively (requires prior push --include-raw)
vault pull --restore-claude

# Preview what would be restored without writing anything
vault pull --restore-claude --dry-run
```

Path remapping is **automatic**: a session from `/home/alice/repos/project`
is restored to `~/.claude/projects/-home-bob-repos-project/` on the new
machine — no manual editing needed.

## Cross-machine migration

```
# ── Machine A (source) ──────────────────────────────────────────────────────

# Backup Markdown exports + raw Claude JSONL to a private repo
vault push --vault-repo git@github.com:youruser/vault.git --include-raw

# ── Machine B (destination) ─────────────────────────────────────────────────

git clone https://github.com/sbsepul/ai-memory-vault.git
cd ai-memory-vault && python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Download exports and restore Claude sessions (paths re-encoded for this machine)
vault pull --vault-repo git@github.com:youruser/vault.git --restore-claude

# Restart Claude Code — it will pick up the restored sessions automatically
```

The vault stores paths relative to `$HOME` (`repos/dream-home`, not
`/home/alice/repos/dream-home`), so restoration works across different
usernames, operating systems, and home directory layouts.

## Storage formats decoded

### Claude Code (`~/.claude/projects/`)
Each directory name encodes the absolute project path (`-home-user-repos-project`). `vault` decodes this to a relative path (`repos/project`) at extraction time.

### Codex CLI (`~/.codex/`)

Codex stores data across two formats:

**Session files** (`sessions/YYYY/MM/DD/rollout-*.jsonl`) — full conversation history. Messages live inside `event_msg` events with `payload.type` of `user_message`, `agent_message`, or `task_complete`. The `session_meta` event carries `cwd` for the project path.

**SQLite databases** — four files with distinct roles:

| File | Contents | Used by vault |
|---|---|---|
| `memories_1.sqlite` | Auto-generated memory summaries per session | ✅ `vault memories` |
| `state_5.sqlite` | Thread index: `cwd`, `title`, `first_user_message` | ✅ metadata index |
| `logs_2.sqlite` (243 MB) | Internal app debug logs | ❌ ignored |
| `goals_1.sqlite` | Goal tracking (empty in most installs) | ❌ ignored |

## Roadmap

- [x] `vault pull` — restore sessions to a new machine with automatic path remapping
- [x] `vault memories` — surface Codex auto-generated memory summaries from SQLite
- [ ] `vault pull --restore-codex` — restore Codex sessions (SQLite rebuild)
- [ ] `vault serve` — local web viewer for browsing conversations
- [ ] Incremental export (only new sessions since last run)
- [ ] Cursor and Windsurf support

## License

MIT
