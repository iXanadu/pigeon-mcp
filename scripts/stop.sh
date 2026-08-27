#!/bin/bash
# Stop pigeon-mcp HTTP service (user LaunchAgent).
#
# Usage:
#   ./scripts/stop.sh

set -euo pipefail

LABEL="com.pigeon-mcp"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "ERROR: launchd scripts are macOS-only"
    exit 1
fi

if ! launchctl list "$LABEL" &>/dev/null; then
    echo "Service not running"
    exit 0
fi

launchctl unload "$PLIST"
echo "Service stopped"
