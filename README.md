# pigeon-mcp

Gmail connector for MCP clients. One server, many Gmail accounts via OAuth refresh tokens. Sends real MIME (file-path attachments, live signatures, post-send proof). Reads and organises mail without dumping megabytes of base64 into the model.

**Not** a wrapper around Google's hosted Gmail MCP — this builds RFC822 on the host and talks to `gmail.googleapis.com` directly.

**Scope today:** Gmail only. The Google Cloud project may also have **Calendar** and **Drive** APIs enabled for later work — this server does not call them yet. Do not request Calendar/Drive OAuth scopes until those tools ship.

## Features

- **Multi-account OAuth** — add mailboxes with `accounts_add`; tokens stored as `gmail-token-*.json` (mode 0640)
- **Many identities on one mailbox** — `identities_list` reads Gmail's verified send-as list; `from_identity` on send/reply/forward/draft sets `From`, `Reply-To` and the alias's own signature, validated in the handler. See [`docs/mailroom.md`](docs/mailroom.md)
- **Routing headers** — every read exposes `originalTo` (`X-Gm-Original-To`), `deliveredTo`, `replyTo`, `authResults`; `messages_list` sweeps headers without bodies
- **Send / reply / forward** — server-built MIME, outbox file paths only, 25 MB cap, idempotency keys, proof on success
- **Read / organise** — search (threads + pagination), get thread/message, labels, archive/trash, drafts
- **Attachments** — send from configured outbox root (default `~/Outbox`); stage via `POST /outbox/stage` (bearer); download to configured download root (default `~/Inbox`)
- **Dual transport** — stdio for local harnesses; Streamable HTTP behind a gateway for remote clients

## Requirements

- Python 3.12+ (development uses 3.13 via pyenv)
- Google Cloud **Web application** OAuth client (Hand / HTTP consent via public callback)
- macOS for the included LaunchAgent scripts (HTTP service); Linux works for manual runs

## Quick start

```bash
git clone https://github.com/iXanadu/pigeon-mcp.git
cd pigeon-mcp

# Python 3.12+ (example with pyenv)
pyenv virtualenv 3.13 pigeon-mcp-3.13
pyenv local pigeon-mcp-3.13
pip install -e '.[dev]'

# Config (see examples/)
cp examples/config.example .env
cp examples/secrets.example .keys
chmod 600 .keys

# Sanity check
pigeon-doctor
```

Fill in `.keys` with your Google OAuth credentials and an HTTP bearer token before running the HTTP transport.

### Google Cloud Console (one-time)

Hand over HTTP needs a **Web application** OAuth client with redirect
`https://<your-host>/oauth/callback`. Optional **Desktop** client is only for
local stdio `accounts_add` (`http://127.0.0.1:8767/oauth/callback`).

**Full guide** (scopes, the unverified-app warning, Workspace vs personal Gmail,
the 7-day Testing trap, token protection, legal URLs):
[`docs/google-oauth-setup.md`](docs/google-oauth-setup.md)

Quick checklist:

| Step | Where | What |
| --- | --- | --- |
| 1 | APIs & Services → Library | Enable **Gmail API** |
| 2 | OAuth consent screen | **External** → **Publish app** (*In production*). Do **not** stay in Testing (7-day refresh expiry). See the doc for Workspace **Internal**. |
| 3 | Credentials → Create | **OAuth client ID → Web application** |
| 4 | Web client | Redirect **`https://<your-host>/oauth/callback`** → `PIGEON_MCP_OAUTH_PUBLIC_REDIRECT_URI` |
| 5 | `.keys` | Web client id/secret → `PIGEON_MCP_GOOGLE_WEB_CLIENT_ID` / `_SECRET` (see `examples/secrets.example`) |

Privacy / Terms URLs for the consent screen: [`docs/legal/`](docs/legal/README.md)
(c52.com live: `https://pigeon.c52.com/privacy`, `https://pigeon.c52.com/terms`).

On first connect, Google asks for consent. Scopes are fixed in the server: `gmail.modify` + `gmail.send` — read/send/organise mail; `modify` also reads the send-as list (identities, live signature, not cached).

**No** username/password, app password, or pasted refresh token in chat.

### Connect a mailbox

**Hand / HTTP (recommended):** call `accounts_auth_start`, open the returned
`auth_url` in a browser, complete consent — the public `/oauth/callback` route
finishes automatically. Then `accounts_list` over HTTP.

**Local stdio only:** `accounts_add` opens a browser for Google consent. It runs
on the **stdio** transport (`pigeon-mcp`), not over HTTP.

```bash
pigeon-mcp   # stdio — required for accounts_add and accounts_remove
```

Call `accounts_add` from your MCP client. When consent finishes, the server records the Gmail address Google returns; that address is the `account` key for every other tool.

Tokens land in `PIGEON_MCP_TOKENS_DIR` (default `~/.config/pigeon-mcp/tokens/`) as `gmail-token-<account>.json` (mode 0640). On a production host, set `PIGEON_MCP_TOKENS_DIR` to a directory your backup actually sweeps (often next to the app checkout), then copy the token files there.

#### Headless server (no local browser)

The OAuth callback is `http://127.0.0.1:8767/oauth/callback`. A machine with no display still needs a browser **somewhere** for the Google login page. Two common patterns:

**A — SSH port forward (consent on your laptop)**

On the headless host, start stdio MCP / `accounts_add`. From your laptop:

```bash
ssh -L 8767:127.0.0.1:8767 user@headless-host
```

Open the authorization URL the server prints (or trigger `accounts_add` through your MCP client with the tunnel up). The callback hits `127.0.0.1:8767` on the headless host via the tunnel.

**B — Consent on a desktop, copy tokens**

Run `accounts_add` once on a Mac or PC with a browser and the same `.env` / `.keys`. After consent, copy the `gmail-token-*.json` files to the production host’s `PIGEON_MCP_TOKENS_DIR` (mode 0640). No re-consent unless Google revokes the refresh token.

## Deployment layout

Typical production split:

```
┌─────────────────────┐         ┌──────────────────────────┐
│  Operator machine   │         │  MCP server (Linux/macOS) │
│  (browser for OAuth)│         │  pigeon-mcp-http           │
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
- Generate a long random `PIGEON_MCP_HTTP_BEARER_TOKEN`; the gateway presents it as `Authorization: Bearer …`.

After deploy: `pigeon-doctor`, `./scripts/start.sh` (macOS LaunchAgent) or your own systemd unit, then `accounts_list` over HTTP to confirm tokens.

## Configuration

Non-sensitive settings live in `.env`; secrets in `.keys` (never commit either when populated). Templates: `examples/config.example` and `examples/secrets.example`.

| Variable | File | Purpose |
| --- | --- | --- |
| `PIGEON_MCP_ENVIRONMENT` | `.env` | Label for logs/status |
| `PIGEON_MCP_LOG_LEVEL` | `.env` | Server log level |
| `PIGEON_MCP_HTTP_HOST` | `.env` | HTTP bind address (default `127.0.0.1`) |
| `PIGEON_MCP_HTTP_PORT` | `.env` | HTTP port (default `8879`) |
| `PIGEON_MCP_OUTBOX_ROOT` | `.env` | Send/stage attachment paths (pick per machine; `/tmp/...` fine on personal hosts) |
| `PIGEON_MCP_DOWNLOAD_ROOT` | `.env` | `get_attachment` writes |
| `PIGEON_MCP_TOKENS_DIR` | `.env` | OAuth token storage directory |
| `PIGEON_MCP_OAUTH_REDIRECT_URI` | `.env` | OAuth loopback callback (stdio Desktop client) |
| `PIGEON_MCP_OAUTH_PUBLIC_REDIRECT_URI` | `.env` | Public HTTPS callback (Web client / Hand) |
| `PIGEON_MCP_GOOGLE_WEB_CLIENT_ID` | `.keys` | Google Web OAuth client id |
| `PIGEON_MCP_GOOGLE_WEB_CLIENT_SECRET` | `.keys` | Google Web OAuth client secret |
| `PIGEON_MCP_GOOGLE_CLIENT_ID` | `.keys` | Optional Desktop client (stdio) |
| `PIGEON_MCP_GOOGLE_CLIENT_SECRET` | `.keys` | Optional Desktop client secret |
| `PIGEON_MCP_HTTP_BEARER_TOKEN` | `.keys` | Bearer token for HTTP transport |

Run `pigeon-doctor` after changing config.

## Transports

### stdio (local)

```bash
pigeon-mcp
```

Registers **all** tools, including `accounts_add` and `accounts_remove`.

Wire into Cursor / Claude Code MCP config with the venv `pigeon-mcp` binary and `cwd` set to the repo (so `.env` / `.keys` load).

### Streamable HTTP (gateway)

```bash
pigeon-mcp-http
```

Binds `127.0.0.1:8879` by default. Requires `Authorization: Bearer <PIGEON_MCP_HTTP_BEARER_TOKEN>`; requests without a valid token get **401**.

**Hand allow-list** (HTTP only): read/organise tools plus `send`, `reply`, `forward`, `draft_create`, `draft_send`, `identities_list`, `messages_list`, `accounts_list`, `accounts_auth_start`, and `gmail_status`. Account management (`accounts_add` / `accounts_remove`) stays on stdio.

**Stage attachments for Hand** (no scp required):

```bash
curl -sS -X POST "https://pigeon.c52.com/outbox/stage?filename=deed.pdf" \
  -H "Authorization: Bearer $PIGEON_MCP_HTTP_BEARER_TOKEN" \
  --data-binary @deed.pdf
# → {"path":".../deed.pdf","filename":"deed.pdf","size":N,...}
```

Then call `send` / `reply` / `forward` with `attachments_json` using that `path`. Proxy must expose `/outbox/stage` (same bearer as `/mcp`). Cap: 25 MB.

#### macOS service (user LaunchAgent)

```bash
./scripts/start.sh    # install plist → ~/Library/LaunchAgents, load
./scripts/stop.sh
./scripts/restart.sh
```

Edit `launchd/com.pigeon-mcp.plist` paths if your checkout or pyenv name differs. Logs go to `logs/`.

On Linux, run `pigeon-mcp-http` under systemd with the same loopback bind — see **Deployment layout** above.

## Tools

| Tool | Notes |
| --- | --- |
| `gmail_status` | Version and config summary |
| `accounts_list` | Connected addresses and token health |
| `accounts_add` | OAuth consent (**stdio only**) |
| `accounts_remove` | Revoke and drop token (**stdio only**) |
| `identities_list` | Verified send-as identities for an account — the only values `from_identity` accepts |
| `search` | Gmail query; returns threads |
| `messages_list` | Gmail query; returns messages with headers + snippet, no bodies (routing sweeps) |
| `get_thread` / `get_message` | `format=metadata` (headers only), `plain` or `full`; every message carries `originalTo`, `deliveredTo`, `replyTo`, `authResults` |
| `get_attachment` | Writes under download root |
| `send` / `reply` / `forward` | Paths only; rejects `content` / base64 in JSON; optional `from_identity` |
| `draft_create` / `draft_send` | Same attach/proof rules as send; `draft_create` takes `from_identity` |
| `labels_list` / `labels_create` | User + system labels |
| `label` / `unlabel` | Comma-separated names or ids |
| `archive` / `trash` / `untrash` | Thread-level |

Every tool except `accounts_list`, `accounts_add`, and `gmail_status` requires an `account` argument (the Gmail address).

## Send rules (summary)

- Stage remote files first: `POST /outbox/stage` (bearer) → use returned `path`
- Attachments: `{ "path": "/absolute/or/under/outbox/file.pdf" }` — no inline base64
- `from_identity` (optional): a verified send-as address on the account — sets `From` with display name and `Reply-To`; rejected in the handler if not in `identities_list`
- Live Gmail signature of the sending identity appended at send time (not cached)
- Optional `footer` after signature
- Returns proof: sizes, hrefs, `ok` false → tool error (e.g. chopped attachment or `google.com/url` rewrite)

## Tests

```bash
pytest tests/ -v
```

Uses mocked Gmail HTTP; no live mailbox required.

## Mailroom: one mailbox, many agents

Give each agent its own address on one mailbox (Workspace catch-all + send-as, or consumer plus-addressing), route inbound on `originalTo`, trust only recipients in `identities_list`, send with `from_identity`. Full pattern, setup steps, label scheme and the do-not-attempt list: [`docs/mailroom.md`](docs/mailroom.md).

## Spec

Product requirements: `docs/specs/gmail-mcp-spec.md`

## License

Apache-2.0
