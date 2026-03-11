#!/bin/bash

set -euo pipefail

cd "$(dirname "$0")"

VENV_DIR=".venv_local"
INSTALL_DEPS="${INSTALL_DEPS:-0}"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    python3 -m venv "$VENV_DIR"
fi

if [ "$INSTALL_DEPS" = "1" ]; then
    "$VENV_DIR/bin/python" -m pip install -r requirements.txt
fi

exec "$VENV_DIR/bin/python" run.py
