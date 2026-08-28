# pigeon-mcp

## Project Overview
Gmail connector for MCP: one tool module, two transports (stdio for local harnesses, Streamable HTTP behind a gateway for remote clients). OAuth refresh-token auth, N Gmail identities, server-built MIME, file-path attachments, live signatures.

**READ FIRST:** `docs/specs/pigeon-mcp-spec.md` (acceptance criteria), then `README.md` (operator setup).

## Project Structure
```
pigeon-mcp/
├── AGENTS.md
├── CLAUDE.md         # symlink -> AGENTS.md
├── src/pigeon_mcp/    # MCP server, config, doctor
├── tests/
├── scripts/          # start/stop/restart, resolve-venv-python
├── docs/specs/       # product spec
├── examples/         # config.example / secrets.example
├── .env              # non-secret (not committed)
├── .keys             # secrets (not committed)
└── pyproject.toml    # entrypoints: pigeon-mcp, pigeon-mcp-http, pigeon-doctor
```

## Commands
```bash
pyenv virtualenv 3.13 pigeon-mcp-3.13
pyenv local pigeon-mcp-3.13
pip install -e '.[dev]'
pytest tests/ -v
pigeon-doctor
```

## Conventions
- Config: `.env` (non-sensitive) + `.keys` (secrets, never commit). Prefix `PIGEON_MCP_`.
- Python: pyenv + pyenv-virtualenv (not `python -m venv`). Venv name: `pigeon-mcp-3.13`.
- No database. Tokens are `gmail-token-*.json` under `PIGEON_MCP_TOKENS_DIR` (default `~/.config/pigeon-mcp/tokens`), mode 0640.
- Attachments only from outbox root (default `~/Outbox`).
- Public routes: `/mcp`, `/oauth/callback`, `/outbox/stage`, `GET /healthz`

## Deployment Workflow
1. Work locally, commit, push
2. On the server host: `sudo -v && ./deploy/deploy.sh` (see `deploy/DEPLOYING.md`) — pull, install, restart, verify, auto-rollback
3. Marketing-only: `./deploy/deploy-static.sh` then purge CDN if pages 404 stale
4. Record any post-pull host actions for the next operator session

## Sources of Truth
- `deploy/DEPLOYING.md` — how to ship (app + static); app requirements for deployability
- `BACKLOG.md` — open items only (if it is not there, it is not tracked)
- `docs/specs/pigeon-mcp-spec.md` — acceptance criteria
- engram `scope=project` — session/deploy state (not git)

## Reference Docs
- `README.md` — install, quick OAuth checklist
- `docs/google-oauth-setup.md` — scopes, consent screen, Testing trap, legal URLs
- `docs/legal/` — Privacy + Terms (repo copies; live on pigeon.c52.com)
- `docs/specs/pigeon-mcp-spec.md` — acceptance criteria
- `scripts/repo-hygiene-check.sh` — assume-public gate (local `.hygiene-denylist`, never commit)
