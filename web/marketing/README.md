# Marketing site (pigeon)

Public pages for `pigeon.c52.com`. **Visual identity is pigeon’s own** (Fraunces + Figtree, cool mist + amber accent) — not a Share skin.

| File | Role |
| --- | --- |
| `index.html` | Overview landing |
| `how-it-works.html` | OAuth → MCP → stage → send |
| `for-agents.html` | Hand / agent seat instructions |
| `privacy.html` / `terms.html` | Consent-screen HTML (source also in `docs/legal/`) |
| `site.css` | Pigeon look |
| `favicon.svg` | Tab icon |

## Deploy

Serve this directory at the public host document root for `/`, and map:

- `/` → `index.html`
- `/how-it-works` → `how-it-works.html` (or keep `.html`)
- `/for-agents` → `for-agents.html`
- `/privacy` → `privacy.html`
- `/terms` → `terms.html`

Keep `/mcp`, `/oauth/callback`, `/outbox/stage`, `/healthz` on the app — not these static files.
