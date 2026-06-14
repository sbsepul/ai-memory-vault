# Contributing to AI Memory Vault

## Contributor setup

```bash
git clone https://github.com/sbsepul/ai-memory-vault.git
cd ai-memory-vault
uv sync --extra dev
pre-commit install
```

Validate the package before opening a PR:

```bash
uv run ruff check . --fix
uv run ruff format .
uv run isort .
uv run python -m compileall src
```

## Project structure

```text
src/ai_memory_vault/
├── domain/          # stable business objects and reports
├── application/     # orchestration and reusable use cases
├── infrastructure/  # filesystem, sqlite, git, export adapters
├── interfaces/      # CLI entrypoints and future delivery channels
├── extractors/      # backward-compatible adapter imports
├── exporters/       # backward-compatible adapter imports
├── sync/            # backward-compatible adapter imports
└── cli.py           # thin compatibility entrypoint
```

### Design rules

- `domain/` must stay free of CLI, filesystem, git, and rich rendering concerns.
- `application/` coordinates workflows and filtering.
- `infrastructure/` is where raw tool formats, sqlite access, git sync, and filesystem writes belong.
- `interfaces/` should stay thin. If logic starts growing there, move it down a layer.

## Adding support for a new AI tool

1. Add the extractor under `infrastructure/extractors/`.
2. Normalize everything into `domain.models.Session`.
3. Register the source in `config.py`.
4. Wire it into `application/session_loader.py`.
5. Optionally expose a compatibility wrapper under `extractors/` if you want to preserve legacy imports.

The rule is simple: new tools should plug into the same domain contract, not add special cases inside CLI commands.

## Tooling

- `ruff` handles linting and formatting.
- `isort` keeps imports stable.
- `pre-commit` runs local guardrails before each commit.

If you add new commands or architecture layers, update both the README and this file so the public structure stays accurate.

## Pull requests

1. Open an issue first for non-trivial changes.
2. Keep refactors and features separated when possible.
3. Run the full local checks before opening the PR.
4. Describe user-visible impact and architecture impact in the PR body.
