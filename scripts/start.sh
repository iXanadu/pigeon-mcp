#!/bin/bash
# Start pigeon-mcp HTTP service (user LaunchAgent).
#
# Usage:
#   ./scripts/start.sh

set -euo pipefail

LABEL="com.pigeon-mcp"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
PLIST_SRC="$APP_DIR/launchd/com.pigeon-mcp.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "ERROR: launchd scripts are macOS-only"
    exit 1
fi

mkdir -p "$APP_DIR/logs"

PF_PY="$("$SCRIPT_DIR/resolve-venv-python.sh" python)"
HTTP_BIN="$(cd "$APP_DIR" && "$PF_PY" -c 'import shutil,sys; p=shutil.which("pigeon-mcp-http"); print(p or "")')"
if [[ -z "$HTTP_BIN" ]]; then
    echo "ERROR: pigeon-mcp-http not on PATH for $PF_PY — run: pip install -e ."
    exit 1
fi

if ! (cd "$APP_DIR" && "$PF_PY" -m pigeon_mcp.doctor); then
    echo
    echo "Doctor reported warnings — fix before production. Continuing for local dev."
fi
echo

# Always refresh the installed plist from this checkout (paths move on rename).
USERNAME="$(whoami)"
sed \
    -e "s|__PIGEON_HTTP_BIN__|$HTTP_BIN|g" \
    -e "s|__PIGEON_APP_DIR__|$APP_DIR|g" \
    -e "s|__PIGEON_HOME__|$HOME|g" \
    -e "s|YOUR_USERNAME|$USERNAME|g" \
    "$PLIST_SRC" > "$PLIST_DEST"
echo "Installed LaunchAgent → $PLIST_DEST"

# Prefer modern bootout/bootstrap; fall back to load.
UID_NUM="$(id -u)"
if launchctl print "gui/${UID_NUM}/${LABEL}" &>/dev/null; then
    launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
fi
if launchctl bootstrap "gui/${UID_NUM}" "$PLIST_DEST" 2>/dev/null; then
    launchctl enable "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
    launchctl kickstart -k "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
else
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    launchctl load "$PLIST_DEST"
fi

echo "Service started (Streamable HTTP — see $APP_DIR/logs/pigeon-mcp.log)"
