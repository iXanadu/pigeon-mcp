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
if ! (cd "$APP_DIR" && "$PF_PY" -m pigeon_mcp.doctor); then
    echo
    echo "Doctor reported warnings — fix before production. Continuing for local dev."
fi
echo

if [[ ! -f "$PLIST_DEST" ]]; then
    if [[ ! -f "$PLIST_SRC" ]]; then
        echo "ERROR: Plist template missing at $PLIST_SRC"
        exit 1
    fi
    USERNAME="$(whoami)"
    sed \
        -e "s|YOUR_USERNAME|$USERNAME|g" \
        "$PLIST_SRC" > "$PLIST_DEST"
    echo "Installed LaunchAgent → $PLIST_DEST"
fi

if launchctl list "$LABEL" &>/dev/null; then
    echo "Service already running. Use ./scripts/restart.sh to restart."
    exit 0
fi

launchctl load "$PLIST_DEST"
echo "Service started (Streamable HTTP on 127.0.0.1:8879)"
