# gmail-mcp

## Project Overview
Gmail connector for MCP: one tool module, two transports (stdio for local harnesses, Streamable HTTP behind a gateway for remote clients). OAuth refresh-token auth, N Gmail identities, server-built MIME, file-path attachments, live signatures.

**READ FIRST:** `docs/specs/gmail-mcp-spec.md` (acceptance criteria), then `README.md` (operator setup).

## Project Structure
```
gmail-mcp/
├── AGENTS.md
├── CLAUDE.md         # symlink -> AGENTS.md
├── src/gmail_mcp/    # MCP server, config, doctor
├── tests/
├── scripts/          # start/stop/restart, resolve-venv-python
├── docs/specs/       # product spec
├── examples/         # config.example / secrets.example
├── .env              # non-secret (not committed)
├── .keys             # secrets (not committed)
└── pyproject.toml    # entrypoints: gmail-mcp, gmail-mcp-http, gmail-doctor
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
- Python: pyenv + pyenv-virtualenv (not `python -m venv`). Venv name: `gmail-mcp-3.13`.
- No database. Tokens are `gmail-token-*.json` under `GMAIL_MCP_TOKENS_DIR` (default `~/.config/gmail-mcp/tokens`), mode 0640.
- Attachments only from outbox root (default `~/Outbox`).
- Public routes: `/mcp`, `/oauth/callback`, `/outbox/stage`, `GET /healthz`

## Deployment Workflow
1. Work locally, commit, push
2. On the server host: `git pull`, install editable into the host venv, restart the service
3. Record any post-pull host actions for the next operator session

## Reference Docs
- `README.md` — install, quick OAuth checklist
- `docs/google-oauth-setup.md` — scopes, consent screen, Testing trap, legal URLs
- `docs/legal/` — Privacy + Terms (repo copies; live on gmcp.c52.com)
- `docs/specs/gmail-mcp-spec.md` — acceptance criteria
