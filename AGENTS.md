# gmail-mcp

## Project Overview
Gmail connector for MCP: one tool module, two transports (stdio for local harnesses, Streamable HTTP behind the gateway for Hand). OAuth refresh-token auth, N Gmail identities, server-built MIME, file-path attachments, live signatures.

**READ FIRST, in this order:** `docs/specs/gmail-mcp-spec.md` (the owner's spec — source of truth, blocking tests 2/3/8) then `docs/specs/gmail-mcp-spec-review.md` (pre-build review: 10 gaps, 5 of which change the build — resolve each with the owner/PM, never silently adopt or skip). Reference implementation to copy the shape from: `~/projects/engram/integrations/claude-code/`.

## Project Structure
```
projectname/
├── AGENTS.md         # This file — project identity. Read by ALL providers.
├── CLAUDE.md         # symlink -> AGENTS.md (Claude Code compat)
├── skills/           # init, startup, wrapup as SKILL.md files
├── .claude/
│   └── skills        # symlink -> ../skills (Claude Code discovery)
├── docs/                 # Reference docs and specs
│   ├── CANONICAL-DOCS.md # pointer to the shared bibles/ — never copied per-project
│   └── specs/            # PRD, feature specs, technical requirements
├── .env              # Non-sensitive config (not committed)
├── .keys             # Secrets (not committed)
├── .python-version   # pyenv virtualenv name
└── requirements.txt
```

## Commands
```bash
# Python environment
pyenv virtualenv 3.13 projectname-3.13
pyenv local projectname-3.13
pip install -r requirements.txt

# Run tests
pytest tests/ -v
```

## Conventions
- Config: `.env` (non-sensitive) + `.keys` (secrets, never commit)
- Python: pyenv + pyenv-virtualenv (NEVER `python -m venv`)
- Virtualenv naming: `{project}-{major}.{minor}`
- Database: PostgreSQL (no SQLite, even for local dev)

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
