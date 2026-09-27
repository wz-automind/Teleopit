#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/lib/conda_env.sh"
require_teleopit_python
cd "$ROOT_DIR"
exec "$TELEOPIT_PYTHON" "$ROOT_DIR/scripts/run/run_sim_rh56e2.py" "$@"
