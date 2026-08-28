# pigeon-mcp backlog

Last updated: 2026-08-28 (stable wrap)

Open items only. Host topology and session state live in engram (`startup/next`, `deploy/*`).

## Open

- [ ] Public gateway: wire `/healthz` (loopback 200; `https://pigeon.c52.com/healthz` still 404 — nginx location)
- [ ] First live **send** from the production host after OAuth heal (mailboxes active @ `79b6a5c`; send still the acceptance proof)
- [ ] Retire legacy `gmcp.c52.com` hostname (still proxied toward the old workstation path historically — confirm and remove)
- [ ] Optional smoke: inbound `get_attachment`; large zip under Gmail’s ~25MB cap
- [ ] Dead-simple README pass for first-time agent seats (Web-first OAuth; Desktop as footnote only — see memory `decision/oauth-docs-web-first`)
- [ ] Admin: drop unit `ExecStartPost` chmod workaround now that app `#5` (no chmod `tokens_dir`) is in prod since `c48c121`
- [ ] Owner decision: git-history scrub of old fleet crumbs (no force-push without explicit go)

## Parked

- Re-publishing a public MCP OAuth authorization server / Connect card (owner freeze)
- Multi-tenant SaaS on the reference host (self-host is the product offer)

## Done recently (do not re-open)

- **Marketing press refresh:** landing-refresh kit → live `e3e5948` / `?v=fix5` — mast layout, hero unsquashed, Hand scrubbed, your-server H1/aside balance; owner + GrokBot accepted
- **Follow-author chip:** cooksbayouboy on all marketing pages (`d2ce2f5` chain)
- **OAuth mass `needs_auth`:** refresh used empty Desktop client on Web-only prod — fixed `79b6a5c`, deployed prod-host, three mailboxes healed without re-consent
- Product rename → `pigeon-mcp` / `pigeon.c52.com`; package `PIGEON_MCP_*`
- Deploy playbook in-repo (`deploy/`); prod-host app @ `79b6a5c`, static @ `e3e5948`
- Marketing GrokBot testimony aside + `your-server` VPS on-ramp (pre-refresh)
- App deploy reqs: `/healthz`, env-only boot, expanduser `#4`, no tokens_dir chmod `#5`
- Mini HTTP stopped on purpose after prod cutover
- Public `/favicon.svg` and `/favicon.png` (200 @ 2026-08-28); nginx `/assets/` + favicon.png allowlisted; bare asset URLs 200 at wrap

## References

- `README.md` — operator setup
- `docs/specs/pigeon-mcp-spec.md` — acceptance criteria
- `deploy/DEPLOYING.md` — operator deploy contract (`sudo -n true`, not `sudo -v`)
- engram `startup/next`, `session/2026-08-28-marketing-stable-wrap`
