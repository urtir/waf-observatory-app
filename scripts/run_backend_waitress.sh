#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
BACKEND_DIR="$PROJECT_ROOT/backend"

if [[ ! -d "$BACKEND_DIR/.venv-wsl" ]]; then
  python3 -m venv "$BACKEND_DIR/.venv-wsl"
fi

source "$BACKEND_DIR/.venv-wsl/bin/activate"

cd "$BACKEND_DIR"
exec python -c 'from app import app; from waitress import serve; serve(app, host="127.0.0.1", port=5000)'
