# Marketing site (pigeon)

Cousin layout to [Share](https://share.c52.com/) (`ShareWeb/web/marketing`).

| File | Role |
| --- | --- |
| `index.html` | Overview landing |
| `how-it-works.html` | OAuth → MCP → stage → send |
| `for-agents.html` | Hand / agent seat instructions |
| `privacy.html` / `terms.html` | Consent-screen HTML (source also in `docs/legal/`) |
| `site.css` | Shared visual language with Share |

**Working product name:** `pigeon` (better name TBD — do not bike-shed in this folder).

## Deploy (WebOne)

Serve this directory (or copies) at the public host document root for `/`, and map:

- `/` → `index.html`
- `/how-it-works` → `how-it-works.html` (or keep `.html`)
- `/for-agents` → `for-agents.html`
- `/privacy` → `privacy.html`
- `/terms` → `terms.html`

Keep `/mcp`, `/oauth/callback`, `/outbox/stage`, `/healthz` on the app — not these static files.
