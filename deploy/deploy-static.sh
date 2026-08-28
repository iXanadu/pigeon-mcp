#!/usr/bin/env bash
# Deploy pigeon's marketing pages from the app repo to the nginx static root.
#
# WHY THIS EXISTS: the pages are NOT a separate project. They live in the app
# repo at web/marketing/ and are maintained by whoever maintains the app. The
# only thing that was missing was a repeatable way to get them onto the box —
# the first deploy was a hand-typed `cp`, which is exactly how a site silently
# drifts from its source.
#
# Run after any `git pull` in the app checkout.
set -euo pipefail
SRC=/var/www/gmcp.c52.com/prod/web/marketing
DST=/var/www/pigeon-static
VHOST=/etc/nginx/sites-available/pigeon_c52_prod

[ -d "$SRC" ] || { echo "STOP: $SRC missing — did the repo layout change?"; exit 1; }

# README.md is repo documentation, not a web page. Copy assets explicitly rather
# than mirroring the directory, so a new file cannot become publicly reachable
# just by appearing in the repo.
sudo install -o www-data -g www-data -m 0644 "$SRC"/*.html "$SRC"/*.css "$DST"/
sudo rm -f "$DST"/README.md

echo "deployed:"; ls -1 "$DST" | sed 's/^/  /'

# nginx serves an ALLOWLIST of exact paths — a page in the directory that has no
# location block is a 404. Catch that here rather than via a user reporting it.
echo "checking every page has a route:"
miss=0
for f in "$DST"/*.html; do
  b=$(basename "$f" .html)
  [ "$b" = "index" ] && continue
  if ! grep -q "location = /$b\b" "$VHOST"; then
    echo "  ⚠️  /$b has NO location block — it will 404. Add one to $VHOST"
    miss=1
  else
    echo "  ok /$b"
  fi
done
[ "$miss" -eq 0 ] && echo "all pages routed" || echo "SOME PAGES WILL 404 — see above"

echo
echo "NOTE: Cloudflare caches. After changing a page or adding one, purge it, or"
echo "you will serve a stale 404 for a file that now exists (happened 2026-08-27)."
