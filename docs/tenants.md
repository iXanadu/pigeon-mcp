# Tenants — one pigeon, many agents

A new operator should read this after the Google OAuth client is in `.keys` and
`pigeon-mcp-http` is reachable at `https://<your-host>/mcp`.

There are **two different secrets**. Do not mix them up.

| Thing | What it is | Who holds it |
| --- | --- | --- |
| Gmail OAuth file | `gmail-token-*.json` on the server | pigeon only — never chat, never a laptop config |
| Tenant bearer | `pgn_…` (or the env token seeded as `grokbot`) | one agent. It only sees mailboxes you **grant** |

One mailbox can be granted to several tenants. One tenant must not see a mailbox
you did not grant. That is the point: GrokBot can hold every box you connected;
Cursor should hold only the agent mailbox.

## 1. First bearer (GrokBot / operator agent)

Put a long random value in `.keys` as `PIGEON_MCP_HTTP_BEARER_TOKEN`. On boot,
pigeon hashes it into SQLite as tenant **`grokbot`** and lets that tenant start
Google consent (`accounts_auth_start`).

Give that token to GrokBot (or whichever seat will *connect* mailboxes) the way
it asks — it stores the secret in its own vault and never shows it. Point it at:

```
MCP URL:   https://<your-host>/mcp
```

Then, in conversation: `accounts_auth_start` → you open the Google link on
**your** computer → Allow. The refresh token lands on the server. Repeat for
each mailbox that seat should manage.

Coding agents (Cursor, Claude Code, Codex, Grok CLI) should **not** get this
token and cannot start Google consent unless you tick that on their tenant.

## 2. Owner login (passkey)

You need a pigeon login of your own — not an agent session — to mint the other
tokens.

1. Proxy `/~/` to the app (same as `/mcp`). Without it the dashboard 404s.
2. On the host: `pigeon-admin bootstrap`
3. Open the one-time URL it prints (`https://<your-host>/~/setup?t=…`, 30
   minutes). Register a passkey.
4. After that, sign in at **`https://<your-host>/~/`**.

There is no password. Add a second passkey while you are signed in.

## 3. Mint a tenant per harness

On `/~/`, mint one named bearer per coding agent (`cursor`, `claude`, `codex`,
`grok`, …). Leave **can connect mailboxes** off. Copy the secret **once**.

Grant only the mailboxes that seat may touch (often a single `mail@…` agent
box). GrokBot already has every mailbox that was on disk when the env token
seeded it; you can grant more or revoke from the same page.

The audit log on `/~/` is who called which tool, on which account — not bodies.

## 4. Wire a coding harness (Share pattern)

Do **not** paste `pgn_…` into `mcp.json` / `~/.claude.json` / Codex or Grok
config. Those files are often world-readable.

On the machine that runs the harness:

```
# ~/.config/pigeon-mcp/identities/cursor   (chmod 600)
pigeon_mcp_url=https://<your-host>/mcp
pigeon_api_token=pgn_…
```

Keep a private ledger if you want (`~/.config/Pigeon.keys`); agents read the
identity file, not the ledger.

A small stdio proxy (`~/.local/bin/pigeon-mcp` — copy from this repo's
`scripts/pigeon-mcp-proxy` or the reference host's `~/.local/bin/pigeon-mcp`)
loads `PIGEON_IDENTITY` and POSTs to `/mcp`. The harness config carries the
selector only:

```json
"pigeon": {
  "command": "/Users/you/.local/bin/pigeon-mcp",
  "env": { "PIGEON_IDENTITY": "cursor" }
}
```

Same for Claude (`PIGEON_IDENTITY=claude`), Codex, Grok. A missing identity file
is a hard error — the proxy will not fall back to another harness.

Restart the harness after writing the file. `accounts_list` should show only
granted mailboxes. If it is empty, grant on `/~/`.

## What each seat may do

| Seat | Typical token | Connect a mailbox? | Sees |
| --- | --- | --- | --- |
| GrokBot / operator agent | env bearer (`grokbot`) | Yes | Mailboxes granted to it (all existing files at first boot) |
| Cursor / Claude / Codex / Grok CLI | minted `pgn_…` | No — ask the owner | Only grants you ticked |
| You in a browser | passkey at `/~/` | Grant / revoke / mint / audit | Everything |

If a coding agent says a mailbox is missing, **you** grant it or ask GrokBot for
a new `accounts_auth_start` link. Do not reuse GrokBot’s vault token for a
coding session.

## Files on the host

| Path | What |
| --- | --- |
| `PIGEON_MCP_TOKENS_DIR` / `gmail-token-*.json` | Gmail refresh tokens (0640) |
| `admin.sqlite` (next to that dir, or `PIGEON_MCP_ADMIN_DB`) | Passkeys, hashed bearers, grants, audit |
| `.keys` → `PIGEON_MCP_HTTP_BEARER_TOKEN` | GrokBot seed — rotating it updates the `grokbot` hash |

SQLite on purpose. There is no Postgres for this.
