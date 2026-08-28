# pigeon-mcp backlog

Last updated: 2026-08-28 (wrap)

Open items only. Host topology and session state live in engram (`startup/next`, `deploy/*`).

## Open

- [ ] Public gateway: wire `/healthz` (loopback verify is green; `https://pigeon.c52.com/healthz` still 404)
- [ ] Public gateway: serve `/favicon.svg` (file is in `pigeon-static`; URL still 404 — nginx location and/or CF purge)
- [ ] First live **send** from the production host after OAuth heal (mailboxes active again @ `79b6a5c`; send still the acceptance proof)
- [ ] Retire legacy `gmcp.c52.com` hostname (still proxied toward the old workstation path historically — confirm and remove)
- [ ] Optional smoke: inbound `get_attachment`; large zip under Gmail’s ~25MB cap
- [ ] Dead-simple README pass for first-time agent seats (Web-first OAuth; Desktop as footnote only — see memory `decision/oauth-docs-web-first`)
- [ ] Admin: drop unit `ExecStartPost` chmod workaround now that app `#5` (no chmod `tokens_dir`) is in prod since `c48c121`
- [ ] Owner decision: git-history scrub of old fleet crumbs (no force-push without explicit go)

## Parked

- Re-publishing a public MCP OAuth authorization server / Connect card (owner freeze)
- Multi-tenant SaaS on the reference host (self-host is the product offer)

## Done recently (do not re-open)

- **OAuth mass `needs_auth`:** refresh used empty Desktop client on Web-only prod — fixed `79b6a5c`, deployed prod-host, three mailboxes healed without re-consent
- Product rename → `pigeon-mcp` / `pigeon.c52.com`; package `PIGEON_MCP_*`
- Deploy playbook in-repo (`deploy/`); prod-host playbook-tested green @ `3ff005f`
- Marketing Hand fixes + GrokBot testimony aside + `your-server` VPS on-ramp
- App deploy reqs: `/healthz`, env-only boot, expanduser `#4`, no tokens_dir chmod `#5`
- Mini HTTP stopped on purpose after prod cutover

## References

- `README.md` — operator setup
- `docs/specs/pigeon-mcp-spec.md` — acceptance criteria
- `deploy/DEPLOYING.md` — operator deploy contract (`sudo -n true`, not `sudo -v`)
- engram `startup/next`, `session/2026-08-27-pigeon-prod-wrap`
