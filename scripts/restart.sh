#!/bin/bash
# Restart gmail-mcp HTTP service (user LaunchAgent).
#
# Usage:
#   ./scripts/restart.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

"$SCRIPT_DIR/stop.sh" || true
sleep 1
"$SCRIPT_DIR/start.sh"
