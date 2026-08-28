# Marketing site (pigeon)

Public pages for `pigeon.c52.com`. **Visual identity:** tiding press, different edition — Source Serif 4 on paper (`#f3f2f2` / `#FCF2E9`), ink `#201e1d`, cyan `#0088b0`, magenta `#d6006c`. Engraved assets use `mix-blend-mode: multiply`.

| File | Role |
| --- | --- |
| `index.html` | Overview landing (dateline, hero, numbers rail, Hand pull quote) |
| `how-it-works.html` | OAuth → MCP → stage → send |
| `for-agents.html` | Hand / agent seat instructions |
| `your-server.html` | $5 VPS on-ramp (timeline, Linode shot, undo grid) |
| `privacy.html` / `terms.html` | Consent-screen HTML (source also in `docs/legal/`) |
| `site.css` | Shared styles |
| `assets/` | Engraved JPG/PNG kit (`01`–`09`; `07` off-site only; `09` pending owner approval) |
| `favicon.png` | Cropped from `assets/02-mark-bold.jpg` |
| `favicon.svg` | Fallback tab icon |
| `author-avatar.png` | Circular “Follow the author” chip (X) |

Spec and placement notes: `docs/specs/landing-refresh/README.md`.

## Deploy

Serve this directory at the public host document root for `/`, and map:

- `/` → `index.html`
- `/how-it-works` → `how-it-works.html` (or keep `.html`)
- `/for-agents` → `for-agents.html`
- `/your-server` → `your-server.html`
- `/privacy` → `privacy.html`
- `/terms` → `terms.html`

`deploy/deploy-static.sh` copies `assets/` to the static root alongside HTML and CSS.

Keep `/mcp`, `/oauth/callback`, `/outbox/stage`, `/healthz` on the app — not these static files.
