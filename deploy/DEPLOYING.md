# Deploying pigeon-mcp

This directory is the deploy contract: **operators run these scripts, not
hand-typed commands.** It lives in the app repo on purpose — a deploy script
that references an entrypoint or a settings key belongs in the same commit as
the code that renamed it. Ours drifted the first time precisely because it lived
somewhere else.

## Quick start

```bash
cp deploy/deploy.env.example deploy/deploy.env   # edit for this host
sudo -n true && ./deploy/deploy.sh               # latest origin/main
sudo -n true && ./deploy/deploy.sh <sha>         # a specific commit
sudo -n true && ./deploy/deploy.sh --rollback    # previous deploy
```

Prefer `sudo -n true` over `sudo -v`. On hosts with `Defaults use_pty`, `sudo -v`
fails in non-interactive SSH (BatchMode) even when the operator has NOPASSWD —
it still demands a TTY. `sudo -n` succeeds and is what agent/operator automation needs.

`deploy.sh` fetches, checks out, reinstalls into the virtualenv, restarts the
unit, and then **verifies — rolling back automatically if verification fails.**
A bad push must never leave a mail service down while someone reads a traceback.

## What "verified" means, and why these four

| check | reason |
|---|---|
| unit active | table stakes |
| `GET /healthz` → 200 | the app is *serving*, not merely running |
| `POST /mcp` unauthenticated → 401 | **auth still enforced.** A regression that opens this is worse than a crash — it is a mail-sending API on the public internet |
| ≥1 token file present | an empty tokens dir starts fine and serves **zero mailboxes**. "Up" is not "working" |

The token check must run privileged: the tokens directory is mode 0750, so an
unprivileged `find` returns 0 and looks identical to "all mailboxes gone". That
false negative rolled back a healthy deploy the first time we ran this.

## What the app must provide for this to work

These are requirements on the *application*, not on the operator. If a future
change breaks one, deployment breaks:

1. **`GET /healthz`** — unauthenticated, 200, no data. Without it there is no
   probe a watchdog can use: pointing one at an authenticated endpoint means
   `curl -sf` sees the correct 401 as failure and restart-loops a healthy
   service.
2. **Config fully settable from the environment**, with no file required to
   start. Containers and systemd units configure by environment; an app that
   crashes without a dotenv file cannot be deployed that way.
3. **No interactive startup step.** A server has no browser and no operator at a
   prompt.
4. **Absolute paths, or expand `~` yourself.** `pydantic` does not expand a
   leading tilde: it becomes a *relative* path and silently creates a directory
   literally named `~`.
5. **Do not chmod operator-configured directories on startup.** Locking the
   token dir to 0700 on every boot excludes a backup agent that runs as another
   user in a shared group — silently, with the backup still reporting success.

Points 4 and 5 are not hypothetical; both cost us a debugging cycle on the first
real deployment, and 5 silently removed OAuth refresh tokens from backup.
