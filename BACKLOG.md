# pigeon-mcp backlog

Last updated: 2026-09-01 (robots fix on host)

Open items only. Host topology and session state live in engram (`startup/next`, `deploy/*`).

## Open

### NEEDS-DECISION (owner)
- [ ] **Google Console:** remove any leftover `https://gmcp.c52.com/oauth/callback` from the Web client redirect URIs (owner-only surface).
- [ ] **Cloudflare:** `gmcp.c52.com` still resolved to Cloudflare edge IPs at 22:50Z 2026-08-29 — confirm the DNS record is actually deleted (nothing serves it any more: vhost disabled, cert deleted, static dir archived under `/etc/nginx/backups/gmcp-retire-final/`).
- [ ] **Cloudflare Managed robots.txt:** the zone prepends `Disallow: /` for ClaudeBot, GPTBot, CCBot, Bytespider, meta-externalagent, Amazonbot, Applebot-Extended, Google-Extended on an agent-facing site. Twitterbot is not affected. Keep or turn off (Cloudflare dashboard, owner-only).
- [ ] **GitHub dangling objects:** a force-push does not purge old commits from GitHub's object store immediately (reachable by SHA for a while). If that matters, ask GitHub Support to run a GC on the repo; otherwise it ages out.

### DEGRADING
- (none)

## Parked

- Re-publishing a public MCP OAuth authorization server / Connect card (owner freeze)
- Multi-tenant SaaS on the reference host (self-host is the product offer)

## Done recently (do not re-open)

- **History purge (2026-08-29, owner go):** `git filter-repo` replace-text + replace-message over all refs (fleet hostnames, sibling product names, personal name, tailnet label → generic); force-pushed `main` `d58dc96 → fcffdc8`; deleted stale branches `content/your-server-page`, `ops/deploy-kit`; fresh-clone verify = 0 hits; prod re-pointed, reflog expired, gc'd. Pre-purge mirror kept locally outside the repo.
- **`gmcp.c52.com` host retire (2026-08-29):** vhost disabled, LE cert deleted, static dir archived + removed. DNS is the owner's.
- **Backlog sweep (2026-08-29):** public `/healthz` wired (nginx → app, verified 200 via CF); `ExecStartPost` chmod confirmed already absent from the unit; README rewritten Web-first (Desktop = footnote), examples/spec aligned; hygiene gate fully green; inbound attachment smoke (1 MB + 20 MB zip self-send → `get_attachment` SHA-256 match) — which found and fixed `a2ce65e`: relative `output_path` resolved against CWD instead of `download_root`
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
