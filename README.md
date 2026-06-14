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
- **Multiple export formats** — Markdown (human-readable) or JSON (for scripts)
- **Private vault sync** — push exports to any private git repo for backup and cross-machine access

## Why this exists

| Problem | Solution |
|---|---|
| Claude Code history lives in `~/.claude/` (not backed up) | `vault export` → portable Markdown / JSON |
| Codex history lives in `~/.codex/` (no export tool existed) | Built from scratch, handles all Codex event types |
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
│ work/falabella/backend     │ ✅  │ 12s / 4210m │ 87s / 9841m  │      14051 │
│ Downloads/analysis         │ ❌  │ -           │ 7s / 51m     │         51 │
└────────────────────────────┴─────┴─────────────┴──────────────┴────────────┘
```

The `❌` (no-git) rows are exactly the ones you can't recover from version control — those are the most important to back up.

### `vault ls`
List sessions for a specific project.

```bash
vault ls --project dream-home
vault ls --project falabella --source codex --limit 20
```

### `vault search`
Full-text search across all sessions.

```bash
vault search "authentication middleware"
vault search "docker compose" --source codex
vault search "migration" --project falabella --limit 5
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
    └── work/falabella/backend/
        └── 20260601-1219_019e83fc.md
```

### `vault push`
Export and commit everything to a private git repository for backup.

```bash
# First time: point to your private vault repo
vault push --vault-repo git@github.com:youruser/my-private-vault.git

# Subsequent pushes (repo remembered in ~/.config/ai-memory-vault/config.json)
vault push
vault push --source codex --project falabella
```

## Cross-machine migration

```bash
# Machine A (old)
vault export --format json --output ./vault-backup
# commit vault-backup/ to your private repo and push

# Machine B (new)
git clone <private-vault-repo>
# sessions are readable as Markdown, paths are relative to $HOME
```

## Storage formats decoded

### Claude Code (`~/.claude/projects/`)
Each directory name encodes the absolute project path (`-home-user-repos-project`). `vault` decodes this to a relative path (`repos/project`) at extraction time.

### Codex CLI (`~/.codex/sessions/YYYY/MM/DD/`)
Sessions are JSONL files. Messages live inside `event_msg` events with `payload.type` of `user_message`, `agent_message`, or `task_complete`. The `session_meta` event carries `cwd` (used to derive the relative project path) and `session_index.jsonl` provides human-readable thread names.

## Roadmap

- [ ] `vault pull` — restore sessions to a new machine, remapping paths
- [ ] `vault serve` — local web viewer for browsing conversations
- [ ] Incremental export (only new sessions since last run)
- [ ] Cursor and Windsurf support

## License

MIT
