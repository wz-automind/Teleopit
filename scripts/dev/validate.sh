#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/lib/conda_env.sh"
require_teleopit_python
cd "$ROOT_DIR"
"$TELEOPIT_PYTHON" -m compileall -q teleopit scripts tests
"$TELEOPIT_PYTHON" -m pytest tests/ -q
"$TELEOPIT_PYTHON" -m ruff check --select E,F,I --ignore E501 \
  teleopit/sim2real/hands/rh56e2.py teleopit/sim2real/hands/rh56e2_protocol.py \
  teleopit/sim2real/hands/worker.py scripts/dev/check_rh56e2.py \
  tests/test_rh56e2_config.py tests/test_rh56e2_integration.py \
  tests/test_rh56e2_resources.py tests/test_rh56e2_launchers.py tests/test_rh56e2_bundle.py \
  scripts/setup/package_rh56e2.py
