#!/usr/bin/env bash
# pigeon-mcp deploy. Run by ANY operator with sudo — no dedicated admin session
# required, which is the point.
#
#   sudo -n true && ./deploy/deploy.sh            # pull main, install, restart, verify
#   sudo -n true && ./deploy/deploy.sh <sha>      # deploy a specific commit
#   sudo -n true && ./deploy/deploy.sh --rollback # go back to the previous deploy
#
# Use sudo -n, not sudo -v: use_pty + BatchMode makes -v demand a TTY even with NOPASSWD.
#
# It verifies AFTER restarting and AUTOMATICALLY ROLLS BACK if the new code
# fails, so a bad push cannot leave the mailbox service down while you read a
# stack trace. The last-good sha is recorded on every successful deploy.
set -uo pipefail
# host-specific values; see deploy.env.example
HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/deploy.env" ] || { echo "STOP: no deploy.env — copy deploy.env.example and edit"; exit 1; }
# shellcheck disable=SC1091
. "$HERE/deploy.env"
APP="${APP_DIR:?set in deploy.env}"
UNIT="${UNIT:?set in deploy.env}"
VENV="${VENV:?set in deploy.env}"
ORIGIN="${ORIGIN:?set in deploy.env}"
LASTGOOD=$APP/.last-good-sha

say(){ printf "\033[36m==\033[0m %s\n" "$1"; }
ok(){  printf "  \033[32mok\033[0m   %s\n" "$1"; }
bad(){ printf "  \033[31mFAIL\033[0m %s\n" "$1"; }

# git ops need the deploy key owner; file ops need the service group.
g(){ sg "$SERVICE_USER" -c "git -C $APP $*"; }

verify(){   # returns 0 only if the service is genuinely serving
  local rc=0
  systemctl is-active --quiet "$UNIT" || { bad "unit not active"; return 1; }
  [ "$(curl -s -o /dev/null -w '%{http_code}' -m 8 $ORIGIN/healthz)" = 200 ] \
    && ok "/healthz 200" || { bad "/healthz not 200"; rc=1; }
  [ "$(curl -s -o /dev/null -w '%{http_code}' -m 8 -X POST -H 'Content-Type: application/json' \
       -H 'Accept: application/json, text/event-stream' -d '{}' $ORIGIN/mcp)" = 401 ] \
    && ok "/mcp 401 unauthenticated (auth still enforced)" || { bad "/mcp did not 401 — AUTH MAY BE OPEN"; rc=1; }
  # MUST be sudo: the tokens dir is often 0750 service-group, so an unprivileged find
  # returns 0 and looks exactly like "all mailboxes gone". That false negative
  # rolled back a perfectly good deploy the first time this script ran.
  local n; n=$(sudo find "$APP/tokens" -name '*.json' 2>/dev/null | wc -l)
  [ "$n" -gt 0 ] && ok "$n mailbox token(s) still present" || { bad "NO tokens — mailboxes would be gone"; rc=1; }
  return $rc
}

case "${1:-}" in
  --rollback)
    [ -f "$LASTGOOD" ] || { bad "no recorded last-good sha"; exit 1; }
    TARGET=$(cat "$LASTGOOD"); say "rolling back to $TARGET" ;;
  "") TARGET="" ;;
  *)  TARGET="$1" ;;
esac

PREV=$(sg "$SERVICE_USER" -c "git -C $APP rev-parse HEAD")
say "current: ${PREV:0:8}"

say "1/4 fetching"
g fetch origin --prune || { bad "fetch failed (ssh key belongs to ixanadu — run as ixanadu)"; exit 1; }
[ -z "$TARGET" ] && TARGET=$(sg "$SERVICE_USER" -c "git -C $APP rev-parse origin/main")
[ "$TARGET" = "$PREV" ] && { ok "already at ${TARGET:0:8} — nothing to do"; exit 0; }

say "2/4 checking out ${TARGET:0:8}"
g checkout -q --detach "$TARGET" || { bad "checkout failed"; exit 1; }

say "3/4 installing"
sudo -u "$SERVICE_USER" "$VENV/bin/pip" install -q --no-input -e "$APP" 2>&1 | grep -viE 'notice|upgrade pip' || true

say "4/4 restarting + verifying"
sudo systemctl restart "$UNIT"; sleep 6
if verify; then
  echo "$PREV" | sudo tee "$LASTGOOD" >/dev/null
  sudo chown "$SERVICE_USER:$SERVICE_USER" "$LASTGOOD"
  say "DEPLOYED ${TARGET:0:8}  (rollback target recorded: ${PREV:0:8})"
  exit 0
fi

bad "verification failed — ROLLING BACK to ${PREV:0:8}"
g checkout -q --detach "$PREV"
sudo -u "$SERVICE_USER" "$VENV/bin/pip" install -q --no-input -e "$APP" >/dev/null 2>&1
sudo systemctl restart "$UNIT"; sleep 6
if verify; then say "rolled back cleanly — service is healthy on ${PREV:0:8}"; else
  bad "ROLLBACK ALSO FAILED — service is DOWN. sudo journalctl -u $UNIT -n 50"; fi
exit 1
