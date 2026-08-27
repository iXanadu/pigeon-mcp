#!/bin/bash
# Resolve the pyenv virtualenv python for pigeon-mcp.
#
# Usage:
#   ./scripts/resolve-venv-python.sh [python|bin/python]
#
# Override: PIGEON_MCP_VENV=my-venv

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
CMD="${1:-python}"
PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"

if [[ -n "${PIGEON_MCP_VENV:-}" ]]; then
    VENV="$PIGEON_MCP_VENV"
elif [[ -f "$APP_DIR/.python-version" ]]; then
    VENV="$(tr -d '[:space:]' < "$APP_DIR/.python-version")"
else
    VENV="pigeon-mcp-3.13"
fi

if [[ -x "$PYENV_ROOT/versions/$VENV/bin/$CMD" ]]; then
    echo "$PYENV_ROOT/versions/$VENV/bin/$CMD"
    exit 0
fi

if command -v pyenv >/dev/null 2>&1; then
    PY="$(pyenv prefix "$VENV" 2>/dev/null)/bin/$CMD"
    if [[ -x "$PY" ]]; then
        echo "$PY"
        exit 0
    fi
fi

echo "ERROR: pyenv virtualenv '$VENV' not found (set PIGEON_MCP_VENV or .python-version)" >&2
exit 1
