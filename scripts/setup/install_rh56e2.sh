#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ $# != 2 || "$1" != --wheelhouse || ! -d "$2" ]]; then
  echo 'Usage: bash scripts/setup/install_rh56e2.sh --wheelhouse /absolute/path/to/target-wheelhouse' >&2
  exit 2
fi
wheelhouse="$(cd "$2" && pwd)"
sdk_wheel="$wheelhouse/rh56e2_sdk-0.1.0-py3-none-any.whl"
if [[ ! -f "$sdk_wheel" ]]; then
  echo "Missing SDK wheel: $sdk_wheel" >&2
  exit 2
fi
source "$ROOT_DIR/scripts/lib/conda_env.sh"
require_teleopit_python
# No VCS URLs or clone fallback: all wheels must match the target architecture.
"$TELEOPIT_PYTHON" -m pip install --no-index --find-links "$wheelhouse" \
  'setuptools>=64.0' wheel
# Replace a supplied SDK build even when its version is unchanged; leave other packages alone.
"$TELEOPIT_PYTHON" -m pip install --no-index --find-links "$wheelhouse" \
  --force-reinstall --no-deps "$sdk_wheel"
"$TELEOPIT_PYTHON" -m pip install --no-index --find-links "$wheelhouse" \
  'somehand==0.3.0' 'pico-bridge==0.2.1'
"$TELEOPIT_PYTHON" -m pip install --no-index --find-links "$wheelhouse" \
  --no-build-isolation -e "$ROOT_DIR"
"$TELEOPIT_PYTHON" -m pip check
echo 'Python packages installed. Prepare runtime assets and build g1_bridge_sdk separately for real G1 use; see docs/zh/deployment.md.'
