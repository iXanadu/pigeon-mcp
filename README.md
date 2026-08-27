# proj template

Generic Python codebase template for Claude Code. Use this when you're **building a Python application or library** with no specific web framework attached — a CLI, a daemon, a service, a data pipeline, a library.

## When to use this (proj) vs. the other templates

| Template | Use for |
|---|---|
| **proj** | Generic Python codebase — no specific framework |
| **django** | Django web apps (multi-tenant, ORM, templates) |
| **fastapi** | Async APIs (FastAPI + asyncpg) |
| **apple** | Native iOS / macOS apps (Swift / SwiftUI) |
| **ops** | Non-code ops / infra / admin work (no codebase) |

If your project grows into a Django app or an async API, start from `django` or `fastapi` instead. If it's not really a codebase at all (install/configure/administer something), use `ops`.

## Usage

```bash
rsync -a --exclude='.git' --exclude='.DS_Store' --exclude='Icon*' ~/projects/claude-templates/proj/ ~/projects/<newapp>/
cd ~/projects/<newapp>
# Launch Claude Code, then:
/init
```

Or, for a guaranteed-clean copy straight from the committed tree:

```bash
git -C ~/projects/claude-templates archive HEAD:proj | tar -x -C ~/projects/<newapp>
```

`/init` asks for the project name, sets up the pyenv virtualenv, creates the PostgreSQL database, and fills in project identity.

## Stack

- Python 3.13 (pyenv + pyenv-virtualenv) — virtualenv naming `{project}-{major}.{minor}`
- PostgreSQL (no SQLite, even for local dev)
- `requirements.txt` for dependencies
- Config split: `.env` (non-sensitive) + `.keys` (secrets, never committed)

## Lifecycle

Project lifecycle runs through skills, not scripts:

- `/init` — bootstrap a fresh project (virtualenv, database, identity)
- `/startup` — session start: read memory, orient on state
- `/wrapup` — session end: persist state, promote lessons

## State

State is **memory-first** (engram), not files. There are no `CODEBASE_STATE.md`, `CONTEXT_MEMORY.md`, or `session_progress/` files — session state, decisions, and progress live in persistent memory:

- `scope=project` — session state, WIP, project-specific decisions
- `scope=shared` — lessons, patterns, fixes useful across all projects
- `scope=machine` — machine-specific paths, services, env quirks

## Reference docs

- `docs/DevelopmentBible.md` — development philosophy and patterns
- `docs/DEPLOYMENT_STANDARDS.md` — deployment architecture and procedures
- `docs/specs/` — PRD and feature specifications
