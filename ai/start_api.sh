#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$SCRIPT_DIR/.env"

cd "$SCRIPT_DIR"
source venv/bin/activate

if [[ -f "$ENV_FILE" ]]; then
	set -a
	source "$ENV_FILE"
	set +a
fi

if [[ -z "${LLM_API_KEY:-}" ]]; then
	echo "❌ LLM_API_KEY fehlt. Lege ihn in $ENV_FILE ab oder exportiere ihn vor dem Start."
	exit 1
fi

export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
python3 api_server.py