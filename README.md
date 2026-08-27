# gmail-mcp

Gmail connector for MCP clients. One server, many Gmail accounts via OAuth refresh tokens. Sends real MIME (file-path attachments, live signatures, post-send proof). Reads and organises mail without dumping megabytes of base64 into the model.

**Not** a wrapper around Google's hosted Gmail MCP — this builds RFC822 on the host and talks to `gmail.googleapis.com` directly.

## Features

- **Multi-account OAuth** — add mailboxes with `accounts_add`; tokens stored locally (mode 0600)
- **Send / reply / forward** — server-built MIME, outbox file paths only, 25 MB cap, idempotency keys, proof on success
- **Read / organise** — search (threads + pagination), get thread/message, labels, archive/trash, drafts
- **Attachments** — send from `~/Outbox` (configurable); download to `~/Inbox` (configurable)
- **Dual transport** — stdio for local harnesses; Streamable HTTP behind a gateway for remote clients

## Requirements

- Python 3.12+ (development uses 3.13 via pyenv)
- Google Cloud **Desktop** OAuth client (client id + secret)
- macOS for the included LaunchAgent scripts (HTTP service); Linux works for manual runs

## Quick start

```bash
git clone <repo-url> ~/projects/gmail-mcp
cd ~/projects/gmail-mcp

# Virtualenv + editable install
./scripts/install-mcp-wrapper.sh

# Config (see examples/)
cp examples/.env.example .env
cp examples/.keys.example .keys
chmod 600 .keys

# Sanity check
gmail-doctor
```

Fill in `.keys` with your Google OAuth credentials and an HTTP bearer token before running the HTTP transport.

### Google OAuth setup

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/).
2. Enable the **Gmail API**.
3. Configure the **OAuth consent screen** (External is fine for personal use).
4. Create **OAuth client ID → Desktop app**.
5. Add the redirect URI from `.env` (default `http://127.0.0.1:8767/oauth/callback`) to the client.
6. Copy client id and secret into `.keys`.

Scopes requested on consent: `gmail.modify`, `gmail.send`, `gmail.settings.basic` (live send-as signature only).

### Connect a mailbox

Run the stdio server and call `accounts_add` from your MCP client, or use a local harness. A browser opens for Google consent; the connected address becomes the account key for all other tools.

```bash
gmail-mcp   # stdio — required for accounts_add and accounts_remove
```

Tokens are stored under `~/.config/gmail-mcp/tokens/` by default.

## Configuration

Non-sensitive settings live in `.env`; secrets in `.keys` (never commit either when populated). See `examples/.env.example` and `examples/.keys.example`.

| Variable | File | Purpose |
| --- | --- | --- |
| `GMAIL_MCP_ENVIRONMENT` | `.env` | Label for logs/status |
| `GMAIL_MCP_LOG_LEVEL` | `.env` | Server log level |
| `GMAIL_MCP_HTTP_HOST` | `.env` | HTTP bind address (default `127.0.0.1`) |
| `GMAIL_MCP_HTTP_PORT` | `.env` | HTTP port (default `8879`) |
| `GMAIL_MCP_OUTBOX_ROOT` | `.env` | Root for send attachment paths |
| `GMAIL_MCP_DOWNLOAD_ROOT` | `.env` | Root for `get_attachment` writes |
| `GMAIL_MCP_TOKENS_DIR` | `.env` | OAuth token storage directory |
| `GMAIL_MCP_OAUTH_REDIRECT_URI` | `.env` | OAuth loopback callback |
| `GMAIL_MCP_GOOGLE_CLIENT_ID` | `.keys` | Google OAuth client id |
| `GMAIL_MCP_GOOGLE_CLIENT_SECRET` | `.keys` | Google OAuth client secret |
| `GMAIL_MCP_HTTP_BEARER_TOKEN` | `.keys` | Bearer token for HTTP transport |

Run `gmail-doctor` after changing config.

## Transports

### stdio (local)

```bash
gmail-mcp
```

Registers **all** tools, including `accounts_add` and `accounts_remove`.

Wire into Cursor / Claude Code MCP config with the venv `gmail-mcp` binary and `cwd` set to the repo (so `.env` / `.keys` load).

### Streamable HTTP (gateway)

```bash
gmail-mcp-http
```

Binds `127.0.0.1:8879` by default. Requires `Authorization: Bearer <GMAIL_MCP_HTTP_BEARER_TOKEN>`; requests without a valid token get **401**.

**Hand allow-list** (HTTP only): read/organise tools plus `send`, `reply`, `forward`, `draft_create`, `draft_send`, `accounts_list`, and `gmail_status`. Account management stays on stdio.

#### macOS service (user LaunchAgent)

```bash
./scripts/start.sh    # install plist → ~/Library/LaunchAgents, load
./scripts/stop.sh
./scripts/restart.sh
```

Edit `launchd/com.gmail-mcp.plist` paths if your checkout or pyenv name differs. Logs go to `logs/`.

Put a reverse proxy (e.g. Cloudflare + gateway) in front of the HTTP port for remote access — that wiring is deployment-specific.

## Tools

| Tool | Notes |
| --- | --- |
| `gmail_status` | Version and config summary |
| `accounts_list` | Connected addresses and token health |
| `accounts_add` | OAuth consent (**stdio only**) |
| `accounts_remove` | Revoke and drop token (**stdio only**) |
| `search` | Gmail query; returns threads |
| `get_thread` / `get_message` | `format=plain` or `full` |
| `get_attachment` | Writes under download root |
| `send` / `reply` / `forward` | Paths only; rejects `content` / base64 in JSON |
| `draft_create` / `draft_send` | Same attach/proof rules as send |
| `labels_list` / `labels_create` | User + system labels |
| `label` / `unlabel` | Comma-separated names or ids |
| `archive` / `trash` / `untrash` | Thread-level |

Every tool except `accounts_list`, `accounts_add`, and `gmail_status` requires an `account` argument (the Gmail address).

## Send rules (summary)

- Attachments: `{ "path": "/absolute/or/under/outbox/file.pdf" }` — no inline base64
- Live Gmail signature appended at send time (not cached)
- Optional `footer` after signature
- Returns proof: sizes, hrefs, `ok` false → tool error (e.g. chopped attachment or `google.com/url` rewrite)

## Tests

```bash
pytest tests/ -v
```

Uses mocked Gmail HTTP; no live mailbox required.

## Spec

Product requirements: `docs/specs/gmail-mcp-spec.md`

## License

Apache-2.0
