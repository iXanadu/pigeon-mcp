# pigeon-mcp backlog

Last updated: 2026-08-28

Open items only. Operational host detail lives in engram memory, not here.

## Open

- [ ] Wire public gateway `/healthz` to the app bind (deploy verifies loopback; public still 404 at last probe)
- [ ] First live send from the production host (consent done; send unproven)
- [ ] Retire legacy hostname that still proxies the old workstation
- [ ] Optional: inbound `get_attachment` smoke; large zip under Gmail’s ~25MB cap
- [ ] Dead-simple README pass for first-time agent seats
- [ ] Owner decision: git-history scrub of old fleet crumbs (no force-push without explicit go)

## Parked

- Re-publishing a public MCP OAuth authorization server / Connect card (owner freeze)
- Multi-tenant SaaS on the reference host (self-host is the product offer)

## References

- `README.md` — operator setup
- `docs/specs/pigeon-mcp-spec.md` — acceptance criteria
- `deploy/DEPLOYING.md` — operator deploy contract
- engram `scope=project` — session/deploy state
