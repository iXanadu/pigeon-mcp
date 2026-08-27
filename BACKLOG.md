# gmail-mcp backlog

Last updated: 2026-08-27 (wrapup, cursor-3)

## Done (audited PASS)

| Task | Summary |
| --- | --- |
| TASK-1 | Scaffold, pyenv, config split, doctor |
| TASK-2 | OAuth accounts_list/add/remove, token store 0600 |
| TASK-3 | send/reply/forward, MIME, proof, outbox-only attachments |
| TASK-4 | Read/organise, search threads, download_root for attachments |
| TASK-5 | Streamable HTTP 127.0.0.1:8879, bearer 401, Hand allow-list, launchd scripts |
| TASK-6 | Public README + `examples/.env.example` / `.keys.example` |
| README+ | Google Console table, headless OAuth (SSH :8767 / copy tokens), deploy layout |

Tests: **33/33**. Local commits: `2746ebf` (build), `e764966` (README docs). **No git remote yet.**

## Next (priority order)

### 1. OAuth — blocked on browser (owner, AM)

- [ ] Google Cloud: Gmail API, consent screen, Desktop OAuth client, redirect `http://127.0.0.1:8767/oauth/callback`
- [ ] Add test user on consent screen while app is in Testing
- [ ] Put client id/secret in `.keys` on dev-host
- [ ] Run `accounts_add` via stdio — **headless mini needs SSH tunnel** (`ssh -L 8767:127.0.0.1:8767`) or consent on a headed machine, then copy `~/.config/gmail-mcp/tokens/` to prod
- [ ] See README sections *Google Cloud Console* and *Headless server*

### 2. GitHub remote (owner)

- [ ] Create public repo; PM/owner says when to push
- [ ] Never commit `.env`, `.keys`, or token files

### 3. prod-host production deploy (owner + admin@prod-host)

- [ ] Target: **gmcp.c52.com on prod-host** — NOT the dev-host
- [ ] Loopback HTTP behind nginx; `/mcp` only; bearer + edge auth (Cloudflare Access or client cert)
- [ ] Cloudflare rule so MCP clients are not blocked by bot checks
- [ ] Copy OAuth token files from operator machine after consent
- [ ] systemd + pyenv on prod-host (see memory `deploy/prod-host-shape`)
- [ ] admin@prod-host holding folder creation until remote + HTTP side verified

### 4. Live acceptance (owner)

Spec blocking tests 2, 3, 8 — real mailboxes, ≥140 KB PDF, href not google.com/url, live signature change.

## Out of scope / parked

- Pointing Cloudflare/gateway at dev-host (HTTP is loopback only here)
- Share tools, AgentMail, hosted Google Gmail MCP wrapper
- Public push until owner authorizes

## References

- `README.md` — operator + landing-page source
- `docs/specs/gmail-mcp-spec.md` — acceptance criteria
- `memory:startup/next` — session handoff
- `memory:deploy/prod-host-shape` — prod-host runtime shape
