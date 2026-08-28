#!/usr/bin/env bash
# Deploy pigeon's marketing pages from the app repo to the nginx static root.
#
# Run after any successful app deploy (or alone after a marketing-only push).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/deploy.env" ] || { echo "STOP: no deploy.env — copy deploy.env.example and edit"; exit 1; }
# shellcheck disable=SC1091
. "$HERE/deploy.env"

APP="${APP_DIR:?set in deploy.env}"
SRC="${STATIC_SRC:-web/marketing}"
# Allow relative STATIC_SRC
case "$SRC" in
  /*) ;;
  *) SRC="$APP/$SRC" ;;
esac
DST="${STATIC_DST:?set STATIC_DST in deploy.env}"
VHOST="${NGINX_VHOST:-/etc/nginx/sites-available/pigeon_c52_prod}"

[ -d "$SRC" ] || { echo "STOP: $SRC missing — did the repo layout change?"; exit 1; }
[ -d "$DST" ] || sudo mkdir -p "$DST"

# README.md is repo documentation, not a web page. Copy assets explicitly.
sudo install -o www-data -g www-data -m 0644 "$SRC"/*.html "$SRC"/*.css "$DST"/
# Favicon (svg/ico/png) if present
for f in "$SRC"/favicon.svg "$SRC"/favicon.ico "$SRC"/favicon.png; do
  [ -f "$f" ] && sudo install -o www-data -g www-data -m 0644 "$f" "$DST"/
done
sudo rm -f "$DST"/README.md

echo "deployed:"; ls -1 "$DST" | sed 's/^/  /'

echo "checking every page has a route:"
miss=0
for f in "$DST"/*.html; do
  b=$(basename "$f" .html)
  [ "$b" = "index" ] && continue
  if ! grep -qE "location = /$b(\\.html)?\\b|location = /$b\\b" "$VHOST" 2>/dev/null; then
    # Also accept location = /for-agents.html style
    if ! grep -q "location = /$b" "$VHOST" 2>/dev/null; then
      echo "  ⚠️  /$b has NO location block — it will 404. Add one to $VHOST"
      miss=1
      continue
    fi
  fi
  echo "  ok /$b"
done
[ "$miss" -eq 0 ] && echo "all pages routed" || echo "SOME PAGES WILL 404 — see above"

echo
echo "NOTE: Cloudflare caches. After changing a page or adding one, purge it, or"
echo "you will serve a stale 404 for a file that now exists."
