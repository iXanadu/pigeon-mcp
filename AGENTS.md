# gmail-mcp

## Project Overview
Gmail connector for MCP: one tool module, two transports (stdio for local harnesses, Streamable HTTP behind the gateway for Hand). OAuth refresh-token auth, N Gmail identities, server-built MIME, file-path attachments, live signatures.

**READ FIRST, in this order:** `docs/specs/gmail-mcp-spec.md` (the owner's spec — source of truth, blocking tests 2/3/8) then `docs/specs/gmail-mcp-spec-review.md` (pre-build review: 10 gaps, 5 of which change the build — resolve each with the owner/PM, never silently adopt or skip). Reference implementation to copy the shape from: `~/projects/engram/integrations/claude-code/`.

## Project Structure
```
gmail-mcp/
├── AGENTS.md
├── CLAUDE.md         # symlink -> AGENTS.md
├── src/gmail_mcp/    # MCP server, config, doctor
├── tests/            # conftest pins src/
├── scripts/          # install-mcp-wrapper.sh
├── docs/specs/       # owner spec + pre-build review
├── .env              # non-secret (not committed)
├── .keys             # secrets (not committed)
└── pyproject.toml    # package + entrypoints gmail-mcp, gmail-doctor
```

## Commands
```bash
pyenv virtualenv 3.13 gmail-mcp-3.13
pyenv local gmail-mcp-3.13
pip install -e '.[dev]'
pytest tests/ -v
gmail-doctor
```

## Conventions
- Config: `.env` (non-sensitive) + `.keys` (secrets, never commit). Prefix `GMAIL_MCP_`.
- Python: pyenv + pyenv-virtualenv (NEVER `python -m venv`). Venv: `gmail-mcp-3.13`.
- No database. Tokens are files under `~/.config/gmail-mcp/tokens` mode 0600.
- Attachments only from outbox root (default `~/Outbox`).
- Do not bind HTTP on 8766 — that port is Tailscale HTTPS for fleet-registry.

## State Management

**This project uses memory-first state tracking.** No `CODEBASE_STATE.md`, `CONTEXT_MEMORY.md`, or `session_progress/` files. All session state, decisions, and progress live in persistent memory via engram.

Scoping (see global CLAUDE.md for full details):
- `scope=project` — session state, WIP, project-specific decisions
- `scope=shared` — lessons, patterns, fixes useful across all projects
- `scope=machine` — machine-specific paths, services, env quirks

## Deployment Workflow

**Claude does NOT automate server deployment.** The workflow is:
1. Claude and user work locally
2. Code is committed and pushed to repository
3. User manually SSHs to server, runs `git pull`, restarts service
4. When server-side actions are needed after `git pull` (new packages, migrations, env vars, etc.), Claude records them to engram memory (`scope=project`, key `deploy/next`). The server-side Claude reads this via `/startup` after pulling.

## Reference Docs
The shared bibles are NOT copied into projects — they live in one place and would
drift if duplicated. `docs/CANONICAL-DOCS.md` points at them.
- `docs/CANONICAL-DOCS.md` — where the shared bibles live and what's in them
- `docs/specs/` — PRD and feature specifications
