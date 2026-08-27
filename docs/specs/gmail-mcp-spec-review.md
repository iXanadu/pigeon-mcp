# Review notes on `gmail-mcp-spec.md` — 2026-08-26, engram-claude-5

The spec is the owner's document and is the source of truth. These are the
gaps a reviewer found before any code existed, ordered by how much each one
changes what gets built. Items 1–5 change the build; 6–10 are paragraphs.
Resolve each with the owner (or the PM he names) before implementing it —
do not silently adopt or silently skip.

## Decisions already taken (owner, in-session 2026-08-26)

- **Template: `claude-templates/proj`** (generic Python package). Not
  `fastapi` — an MCP server is not an HTTP app; FastMCP ships its own HTTP
  transport, and the fastapi stack drags in Postgres/asyncpg/uvicorn for a
  tool that stores one token file.
- **Reference implementation: the engram MCP bridge**
  (`~/projects/engram/integrations/claude-code/`): `src/` layout with a
  conftest that pins it, console-script entrypoints (`gmail-mcp`,
  `gmail-doctor`), `install-mcp-wrapper.sh` for harness wiring, pyenv
  resolution via `scripts/resolve-venv-python.sh`. Copy the shape.
- **Prior art to inspect, not trust:**
  `~/projects/GoogleClientClasses/GoogleWSClasses/google_gmail.py` (dormant
  since 2026-06-13). Take the OAuth refresh-token code only if it is not
  the code that produced the failures the spec lists.
- **An `mcp` template gets extracted FROM this project once it passes
  acceptance** — not written first. Two real instances (engram bridge,
  this) is when a template is extraction rather than invention.

## 1. Tool names will not survive every client
`accounts.list`, `draft.create` — Claude's tool-name rule is
`^[a-zA-Z0-9_-]{1,64}$`; dots are rejected. Use `accounts_list`,
`draft_create`, etc. One-line change now; a rename across three harness
configs later.

## 2. Attachment-by-path is an arbitrary-file-read when the caller is remote
"Accept file paths, not base64" is the right fix for truncation. But Hand
reaches this server over HTTP from the internet, so "path" means it can ask
the server to email `~/.ssh/id_ed25519` or a token file to any address.
REQUIRED: attachments must resolve (symlinks followed first) under a
configured outbox root (e.g. `~/Outbox/`); anything else is rejected
BEFORE any Gmail call. Acceptance test 9.

## 3. Transport + auth section is missing
The spec reads as a local plugin. Hand is a hosted chat and cannot spawn a
stdio process. REQUIRED:
- One tool module, two transports: stdio for local harnesses (Claude Code,
  Cursor, grok-build), **Streamable HTTP** behind the gateway for Hand.
  FastMCP: `mcp.run()` vs `mcp.run(transport="streamable-http")`.
- The HTTP side is bearer-authenticated with its OWN credential — separate
  from engram's, separate from anything else Hand holds.
- A per-surface tool allow-list. Local Claude and internet Hand must not
  get the same grant by default. Suggested start for Hand: read/organise +
  `draft_create`; open `send`/`trash` deliberately. Owner's own standing
  principle: rules written BEFORE the capability exists.
- PROD HOST IS prod-host (`gmcp.c52.com`, Cloudflare-proxied), NOT the Mac —
  learned from admin@prod-host 2026-08-26 8:48 pm EDT. Deploy follows prod-host's
  standard runtime shape unchanged: uvicorn on a loopback port allocated by
  `/var/www/ports.txt` (never self-claimed), nginx the only edge, systemd
  `uvicorn_gmcp_prod`, pyenv `gmail-mcp-3.12`, `.env` + `.keys`,
  `/var/www/gmcp.c52.com/prod`, Linux user `pigeon_user`. FastMCP's
  Streamable HTTP transport is an ASGI app, so it serves under uvicorn like
  every other prod-host site. Full record: gmail-mcp memory `deploy/prod-host-shape`.
  admin@prod-host is HOLDING provisioning until this repo has a remote and the
  HTTP side runs; ping them on inbox thread `inbox/1748e35a…` when ready.
- The Mac runs only the stdio side for local harnesses (no daemon needed).
- NO OAuth callback route on the vhost: Desktop-client consent runs once per
  account on the owner's Mac (loopback redirect); token files are copied to
  prod-host. Public surface = `/mcp` only.
- SECRETS ON prod-host ARE 0640 app-user:group (ixanadu in the group), NOT the
  spec's 0600: fleet-tools's vault-backup runs as ixanadu every 30 min and a
  0600 file is silently skipped — the token would exist on exactly one
  disk. This overrides the spec's line; the owner has been told why.
- prod-host has no blob backup. Keep no mail cache (spec agrees). The one local
  state file is the idempotency store; single copy accepted, loss = possible
  duplicate send after a restore — say so in the runbook.
- Edge: Cloudflare Browser Integrity Check 403s non-browser clients unless
  the host has its own Configuration Rule (engram and fleet-registry have one;
  share.c52.com lacked one and lost hours today). gmcp needs it before the
  first request, plus a second edge factor (Cloudflare Access service token
  or client cert) on top of the app bearer.

## 4. Duplicate sends
The gateway path retries on timeout; a retried `send` is a second email to
a real person. REQUIRED: caller-supplied `idempotency_key` on `send`,
`reply`, `forward`; server stores key → message id; replay returns the
original id. Acceptance: same key twice → one email.

## 5. The success check measures the wrong thing
"≥90% of source size" lets a 10% truncation pass. Fetch the sent message,
`get_attachment` each part, compare **sha256 to the source file** — exact,
and it exercises the read path. For hrefs: assert on the RAW MIME of the
sent message (`format=raw`). Any RENDERED view of Gmail wraps links by
design; a rendered-view test fails forever and proves nothing.
Keep the spec's recipient-side size check as the gate — that is the
symptom the owner actually lived through.

## 6. The footer belongs to the caller, not the server
A baked-in "Sent by Hand" footer means Claude Code
sending on his behalf also signs as Hand. Make `footer` a parameter with a
per-account default in config; Hand passes its own.

## 7. Scopes
`gmail.modify` already covers send; `gmail.send` is redundant (harmless).
Say why each scope is present. Verify `gmail.settings.basic` is what
`users.settings.sendAs.list` actually requires before consent is done
twice.

## 8. Token lifecycle
Refresh tokens get revoked (password change, Google inactivity rule).
Specify: `invalid_grant` → that account reads `needs-consent` in
`accounts_list`; other accounts unaffected; `accounts_add` re-consents in
place. Otherwise the first revocation reads as "the MCP is broken again".

## 9. Size cap
Gmail rejects >25 MB total. Reject locally with a clear error before the
media upload fails halfway.

## 10. Additional acceptance rows
- HTTP request without the bearer → 401.
- Attachment path outside the outbox root → rejected pre-Gmail.
- Retried `send` with the same idempotency key → exactly one email.
