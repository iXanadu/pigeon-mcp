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
- A Google Cloud **Web application** OAuth client with redirect `https://<your-host>/oauth/callback`
- A Linux or macOS host you control, behind TLS (nginx / Caddy / Cloudflare)

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

Fill in `.keys` with the Web client id/secret and a long random `PIGEON_MCP_HTTP_BEARER_TOKEN`. Set `PIGEON_MCP_OAUTH_PUBLIC_REDIRECT_URI` in `.env` to your public callback.

### Google Cloud Console (one-time)

| Step | Where | What |
| --- | --- | --- |
| 1 | APIs & Services → Library | Enable **Gmail API** |
| 2 | OAuth consent screen | **External** → **Publish app** (*In production*). Do **not** stay in Testing (7-day refresh expiry). See the doc for Workspace **Internal**. |
| 3 | Credentials → Create | **OAuth client ID → Web application** |
| 4 | Web client | Redirect **`https://<your-host>/oauth/callback`** → `PIGEON_MCP_OAUTH_PUBLIC_REDIRECT_URI` |
| 5 | `.keys` | Web client id/secret → `PIGEON_MCP_GOOGLE_WEB_CLIENT_ID` / `_SECRET` |

**Full guide** (scopes, the unverified-app warning, Workspace vs personal Gmail, the 7-day Testing trap, token protection, legal URLs): [`docs/google-oauth-setup.md`](docs/google-oauth-setup.md). Privacy / Terms URLs for the consent screen: [`docs/legal/`](docs/legal/README.md).

Scopes are fixed in the server: `gmail.modify` + `gmail.send` — read/send/organise mail; `modify` also reads the send-as list (identities, live signature, not cached). **No** username/password, app password, or pasted refresh token in chat.

### Connect a mailbox

The agent calls `accounts_auth_start` over HTTP and gets an `auth_url`. A human opens it **on their own computer** (any browser, anywhere — passkeys stay local), picks the Google account, clicks Allow. Google redirects to the public `/oauth/callback`, the server stores the token, and the address shows up in `accounts_list`. That address is the `account` argument for every other tool.

This works on a headless server with no tunnel and no token copying — the callback is a public HTTPS URL, not a loopback. Empty `accounts_list` on a fresh host is success, not a fault.

Tokens land in `PIGEON_MCP_TOKENS_DIR` (default `~/.config/pigeon-mcp/tokens/`) as `gmail-token-<account>.json` (mode 0640). On a production host, point it at a directory your backup sweeps.

<details>
<summary>Optional: local-only stdio with a Desktop client</summary>

If you run pigeon purely on your own machine over stdio and never expose HTTP, you can add a Google **Desktop** OAuth client (redirect `http://127.0.0.1:8767/oauth/callback`) to `.keys` as `PIGEON_MCP_GOOGLE_CLIENT_ID` / `_SECRET` and use `accounts_add`, which opens a local browser. `accounts_add` / `accounts_remove` exist only on the stdio transport. Most deployments do not need this.
</details>

## Deployment layout

```
┌──────────────────────┐        ┌──────────────────────────────┐
│  Any browser         │        │  Your server (Linux/macOS)   │
│  (human clicks Allow)│──────► │  TLS proxy ─► pigeon-mcp-http │
│                      │ /oauth │  127.0.0.1:8879  + .env/.keys │
└──────────────────────┘callback└──────────────┬───────────────┘
                                               │ /mcp  /outbox/stage
                                        agent seat (bearer)
```

- `pigeon-mcp-http` binds **loopback** (`127.0.0.1:8879`); the proxy terminates TLS and forwards `/mcp`, `/outbox/stage`, `/oauth/callback`, `/healthz`.
- The bearer is transport auth: the proxy or the agent presents `Authorization: Bearer …` on `/mcp` and `/outbox/stage`. `/oauth/callback` is public by necessity (a browser redirect carries no bearer); it is protected by single-use `state` + PKCE and only a bearer-authenticated caller can start a flow.
- If you put an access gate (e.g. Cloudflare Access) in front of the host, **exempt `/oauth/callback`** or consent dies after the user clicks Allow.
- In-repo deploy kit for the reference host: [`deploy/DEPLOYING.md`](deploy/DEPLOYING.md).

After deploy: `pigeon-doctor`, start the service (systemd on Linux, `./scripts/start.sh` LaunchAgent on macOS), then `accounts_list` over HTTP.

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
| `PIGEON_MCP_OAUTH_PUBLIC_REDIRECT_URI` | `.env` | Public HTTPS callback — must match the Web client exactly |
| `PIGEON_MCP_GOOGLE_WEB_CLIENT_ID` | `.keys` | Google Web OAuth client id |
| `PIGEON_MCP_GOOGLE_WEB_CLIENT_SECRET` | `.keys` | Google Web OAuth client secret |
| `PIGEON_MCP_HTTP_BEARER_TOKEN` | `.keys` | Bearer token for HTTP transport |
| `PIGEON_MCP_OAUTH_REDIRECT_URI` | `.env` | *Optional, stdio only:* loopback callback for a Desktop client |
| `PIGEON_MCP_GOOGLE_CLIENT_ID` / `_SECRET` | `.keys` | *Optional, stdio only:* Desktop client for local `accounts_add` |

Run `pigeon-doctor` after changing config.

## Transports

### stdio (local harness)

```bash
pigeon-mcp
```

Same tools as HTTP plus `accounts_add` / `accounts_remove` (local Desktop-client consent). Wire into Cursor / Claude Code MCP config with the venv `pigeon-mcp` binary and `cwd` set to the repo (so `.env` / `.keys` load).

### Streamable HTTP (gateway)

```bash
pigeon-mcp-http
```

Binds `127.0.0.1:8879` by default. Requires `Authorization: Bearer <PIGEON_MCP_HTTP_BEARER_TOKEN>`; requests without a valid token get **401**.

**HTTP allow-list:** read/organise tools plus `send`, `reply`, `forward`, `draft_create`, `draft_send`, `identities_list`, `messages_list`, `accounts_list`, `accounts_auth_start`, and `gmail_status`. `accounts_add` / `accounts_remove` stay on stdio.

**Stage attachments** (no scp required):

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
| `accounts_auth_start` | Start Google consent over HTTP; returns `auth_url` for a human |
| `accounts_add` | Local Desktop-client consent (**stdio only**, optional) |
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
