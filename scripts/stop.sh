#!/bin/bash
# Stop pigeon-mcp HTTP service (user LaunchAgent).
#
# Usage:
#   ./scripts/stop.sh

set -euo pipefail

LABEL="com.pigeon-mcp"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
UID_NUM="$(id -u)"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "ERROR: launchd scripts are macOS-only"
    exit 1
fi

if launchctl print "gui/${UID_NUM}/${LABEL}" &>/dev/null; then
    launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
    echo "Service stopped"
    exit 0
fi

if launchctl list "$LABEL" &>/dev/null; then
    launchctl unload "$PLIST" 2>/dev/null || true
    echo "Service stopped"
    exit 0
fi

echo "Service not running"
