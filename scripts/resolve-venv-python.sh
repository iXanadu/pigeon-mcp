#!/bin/bash
# Resolve the pyenv virtualenv python for pigeon-mcp.
#
# Usage:
#   ./scripts/resolve-venv-python.sh [python|bin/python]

set -euo pipefail

VENV="${PIGEON_MCP_VENV:-pigeon-mcp-3.13}"
CMD="${1:-python}"
PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"

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

echo "ERROR: pyenv virtualenv '$VENV' not found" >&2
exit 1
