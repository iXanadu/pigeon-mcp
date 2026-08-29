# pigeon-mcp backlog

Last updated: 2026-08-29 (mailroom identities)

Open items only. Host topology and session state live in engram (`startup/next`, `deploy/*`).

## Open

- [ ] Public gateway: wire `/healthz` (loopback 200; `https://pigeon.c52.com/healthz` still 404 — nginx location)
- [ ] Optional later: drop `gmcp.c52.com` DNS + LE cert + empty `/var/www/gmcp-static` once redirect window is enough (nginx retire vhost live 2026-08-29: pages 301→pigeon, API 410)
- [ ] Owner: remove any leftover `https://gmcp.c52.com/oauth/callback` from Google Cloud Web client redirect URIs (app already uses pigeon only)
- [ ] Optional smoke: inbound `get_attachment`; large zip under Gmail’s ~25MB cap
- [ ] Dead-simple README pass for first-time agent seats (Web-first OAuth; Desktop as footnote only — see memory `decision/oauth-docs-web-first`)
- [ ] Admin: drop unit `ExecStartPost` chmod workaround now that app `#5` (no chmod `tokens_dir`) is in prod since `c48c121`
- [ ] Owner decision: git-history scrub of old fleet crumbs (no force-push without explicit go)

## Parked

- Re-publishing a public MCP OAuth authorization server / Connect card (owner freeze)
- Multi-tenant SaaS on the reference host (self-host is the product offer)

## Done recently (do not re-open)

- **Mailroom LIVE PROOF (2026-08-29, GrokBot seat):** `identities_list` → 6 accepted addresses on the mailroom account; `messages_list` sweeps `originalTo`/`authResults`; `send` with `from_identity` landed as `Hand <hand@…>` with matching `Reply-To`. First prod send done. Page nits fixed `2f36843`
- **Mailroom identities (2026-08-29, deployed `cca660e`):** `identities_list` tool; `from_identity` on send/reply/forward/draft_create (handler-validated, From display name, Reply-To, alias signature); `originalTo`/`deliveredTo`/`replyTo`/`authResults` on reads; `format=metadata`; `messages_list`; dropped `gmail.settings.basic` (modify covers sendAs); `docs/mailroom.md`; README/spec/marketing updated; `grokbot.html` + nav link on all pages; Overview GrokBot CTA; nginx `location = /grokbot` added on `pigeon_c52_prod` (backup `/etc/nginx/backups/pigeon_c52_prod.bak.20260829181658`)
- **`gmcp.c52.com` hostname retire (2026-08-29):** nginx retire vhost — pages 301→`pigeon.c52.com`; MCP/write/OAuth API → 410; admin retargeted SiteWatch to pigeon + bible recaptured (ok 4/4)
- **Marketing press refresh:** landing-refresh kit → live `e3e5948` / `?v=fix5` — mast layout, hero unsquashed, Hand scrubbed, your-server H1/aside balance; owner + GrokBot accepted
- **Follow-author chip:** cooksbayouboy on all marketing pages (`d2ce2f5` chain)
- **OAuth mass `needs_auth`:** refresh used empty Desktop client on Web-only prod — fixed `79b6a5c`, deployed to prod, three mailboxes healed without re-consent
- Product rename → `pigeon-mcp` / `pigeon.c52.com`; package `PIGEON_MCP_*`
- Deploy playbook in-repo (`deploy/`); prod app @ `79b6a5c`, static @ `e3e5948`
- Marketing GrokBot testimony aside + `your-server` VPS on-ramp (pre-refresh)
- App deploy reqs: `/healthz`, env-only boot, expanduser `#4`, no tokens_dir chmod `#5`
- Mini HTTP stopped on purpose after prod cutover
- Public `/favicon.svg` and `/favicon.png` (200 @ 2026-08-28); nginx `/assets/` + favicon.png allowlisted; bare asset URLs 200 at wrap

## References

- `README.md` — operator setup
- `docs/specs/pigeon-mcp-spec.md` — acceptance criteria
- `deploy/DEPLOYING.md` — operator deploy contract (`sudo -n true`, not `sudo -v`)
- engram `startup/next`, `session/2026-08-28-pm-wrap`, `session/2026-08-28-marketing-stable-wrap`
