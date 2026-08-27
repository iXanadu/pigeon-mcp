# Canonical docs — intentionally NOT stored here

The shared dev **bibles** live in ONE place and are never copied into projects
(per-project copies drift and produce contradictory instructions).

- **Location:** `claude-templates/bibles/` — git `iXanadu/claude-templates`, on the dev
  hub at `~/projects/claude-templates`. Authoritative pointer in engram:
  **`reference/canonical-bibles`** (`scope=shared`) — query it if the path moved.
- **What's there:** `DevelopmentBible.md` (general philosophy), `DJANGO_ARCHITECTURE_BIBLE.md`,
  `DJANGO_PROJECT_TEMPLATE.md`, `ENVIRONMENT_SETUP_GUIDE.md`,
  `PROJECT_INITIALIZATION_CHECKLIST.md`. Deployment is **deployment-specific**:
  `DEPLOYMENT_STANDARDS-webapp.md` (nginx+gunicorn via ServerScripts, `/var/www`) and
  `DEPLOYMENT_STANDARDS-service.md` (systemd daemon, `/opt/srv`).

This project's **own** docs (specs, design records, decision logs) stay here in `docs/`.
