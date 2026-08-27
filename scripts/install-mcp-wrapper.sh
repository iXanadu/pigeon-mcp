#!/bin/bash
# Install (or update) the gmail-mcp wrapper into gmail-mcp-3.13.
#
# Safe to re-run; editable install so `git pull && ./scripts/install-mcp-wrapper.sh`
# picks up changes.
#
# Usage:
#   ./scripts/install-mcp-wrapper.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
VENV_NAME="gmail-mcp-3.13"
PYTHON_VERSION="3.13"

echo "=== gmail-mcp install ==="
echo "Repo:   $APP_DIR"

if [ ! -f "$APP_DIR/pyproject.toml" ]; then
    echo "ERROR: $APP_DIR/pyproject.toml not found"
    exit 1
fi

RESOLVE="$HOME/projects/engram/scripts/resolve-venv-python.sh"
if [ ! -x "$RESOLVE" ]; then
    RESOLVE="$(command -v pyenv || true)"
    if [ -z "$RESOLVE" ]; then
        echo "ERROR: pyenv not found"
        exit 1
    fi
    PYENV_BIN="$RESOLVE"
else
    PYENV_ROOT="$("$RESOLVE" --root)" || exit 1
    export PYENV_ROOT
    PYENV_BIN="$("$RESOLVE" --pyenv-bin)" || exit 1
fi

if "$PYENV_BIN" versions --bare 2>/dev/null | grep -q "^${VENV_NAME}$"; then
    echo "venv:   $VENV_NAME (existing)"
else
    PY_FULL=$("$PYENV_BIN" versions --bare 2>/dev/null | grep "^${PYTHON_VERSION}\." | grep -v '/' | sort -V | tail -1)
    if [ -z "$PY_FULL" ]; then
        echo "ERROR: No Python ${PYTHON_VERSION}.x installed in pyenv"
        exit 1
    fi
    echo "venv:   creating $VENV_NAME from Python $PY_FULL..."
    "$PYENV_BIN" virtualenv "$PY_FULL" "$VENV_NAME"
fi

if [ -x "$RESOLVE" ]; then
    VENV_PIP="$("$RESOLVE" "$VENV_NAME" pip)" || exit 1
    VENV_PY="$("$RESOLVE" "$VENV_NAME" python)" || exit 1
else
    VENV_PIP="$PYENV_BIN exec $VENV_NAME pip"
    VENV_PY="$PYENV_BIN exec $VENV_NAME python"
fi

echo "Installing gmail-mcp (editable) into $VENV_NAME..."
"$VENV_PIP" install -e "$APP_DIR[dev]" --quiet

if "$VENV_PY" -c "from gmail_mcp.server import VERSION; print(VERSION)" 2>/dev/null; then
    echo "Verify: gmail_mcp imports cleanly"
else
    echo "ERROR: gmail_mcp import failed"
    exit 1
fi

echo ""
echo "=== Done ==="
echo "Commands: gmail-mcp, gmail-doctor (via $VENV_NAME)"
