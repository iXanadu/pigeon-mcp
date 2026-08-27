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

### Google Cloud Console (one-time)

You need a **Desktop OAuth client** — not a service account, not domain-wide delegation.

| Step | Where | What |
| --- | --- | --- |
| 1 | APIs & Services → Library | Enable **Gmail API** |
| 2 | OAuth consent screen | **External** is fine for personal use. Add your Google account as a **Test user** while the app is in Testing mode. |
| 3 | Credentials → Create | **OAuth client ID → Desktop app** |
| 4 | Client settings | Add redirect URI **`http://127.0.0.1:8767/oauth/callback`** (must match `GMAIL_MCP_OAUTH_REDIRECT_URI` in `.env`) |
| 5 | `.keys` | Paste **Client ID** and **Client secret** as `GMAIL_MCP_GOOGLE_CLIENT_ID` / `GMAIL_MCP_GOOGLE_CLIENT_SECRET` |

On first `accounts_add`, Google asks for consent. Scopes are fixed in the server: read/send/organise mail plus read send-as signature (not cached).

**No** username/password, app password, or pasted refresh token in chat.

### Connect a mailbox (`accounts_add`)

`accounts_add` opens a **browser** for Google consent. It only runs on the **stdio** transport (`gmail-mcp`), not over HTTP.

```bash
gmail-mcp   # stdio — required for accounts_add and accounts_remove
```

Call `accounts_add` from your MCP client. When consent finishes, the server records the Gmail address Google returns; that address is the `account` key for every other tool.

Tokens land in `~/.config/gmail-mcp/tokens/` (mode 0600). Copy that directory to any other host running the same server if needed.

#### Headless server (no local browser)

The OAuth callback is `http://127.0.0.1:8767/oauth/callback`. A machine with no display still needs a browser **somewhere** for the Google login page. Two common patterns:

**A — SSH port forward (consent on your laptop)**

On the headless host, start stdio MCP / `accounts_add`. From your laptop:

```bash
ssh -L 8767:127.0.0.1:8767 user@headless-host
```

Open the authorization URL the server prints (or trigger `accounts_add` through your MCP client with the tunnel up). The callback hits `127.0.0.1:8767` on the headless host via the tunnel.

**B — Consent on a desktop, copy tokens**

Run `accounts_add` once on a Mac or PC with a browser and the same `.env` / `.keys`. After consent, copy `~/.config/gmail-mcp/tokens/` to the production host (same paths, mode 0600). No re-consent unless Google revokes the refresh token.

## Deployment layout

Typical production split:

```
┌─────────────────────┐         ┌──────────────────────────┐
│  Operator machine   │         │  MCP server (Linux/macOS) │
│  (browser for OAuth)│         │  gmail-mcp-http           │
│  accounts_add       │  copy   │  127.0.0.1:8879           │
│  token files ───────┼────────►│  + .env / .keys           │
└─────────────────────┘  tokens └───────────┬──────────────┘
                                            │
                              Cloudflare / gateway / TLS
                                            │
                                    Hand / remote MCP client
```

- **Do not** expose the operator's laptop to the public internet for MCP HTTP. HTTP binds **loopback** (`127.0.0.1:8879`) on the server; a reverse proxy terminates TLS and forwards to that port.
- **OAuth** happens where a browser exists (operator machine or SSH tunnel). Token JSON files are copied to the server.
- **Gateway** points at the **server** hostname you control (e.g. `mcp.example.com`), not the OAuth workstation.
- Generate a long random `GMAIL_MCP_HTTP_BEARER_TOKEN`; the gateway presents it as `Authorization: Bearer …`.

After deploy: `gmail-doctor`, `./scripts/start.sh` (macOS LaunchAgent) or your own systemd unit, then `accounts_list` over HTTP to confirm tokens.

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

On Linux, run `gmail-mcp-http` under systemd with the same loopback bind — see **Deployment layout** above.

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
