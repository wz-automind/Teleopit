#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ "${ENABLE_G1_REAL:-}" != YES ]]; then
  echo 'Refusing real G1 control: set ENABLE_G1_REAL=YES only after operator safety checks. Hand read-only does not make the G1 body read-only.' >&2
  exit 2
fi
if [[ -z "${NETWORK_INTERFACE:-}" || -z "${LEFT_HAND_IP:-}" || -z "${RIGHT_HAND_IP:-}" || "$LEFT_HAND_IP" == "$RIGHT_HAND_IP" ]]; then
  echo 'Set NETWORK_INTERFACE and two distinct LEFT_HAND_IP / RIGHT_HAND_IP values.' >&2
  exit 2
fi
source "$ROOT_DIR/scripts/lib/conda_env.sh"
require_teleopit_python
hand_write=false
if [[ "${ENABLE_RH56E2_WRITES:-}" == YES ]]; then hand_write=true; fi
cd "$ROOT_DIR"
for arg in "$@"; do
  if [[ "$arg" == *hands.rh56e2.write_enabled* ]]; then
    echo 'Use ENABLE_RH56E2_WRITES=YES to enable hand writes, not a Hydra override.' >&2
    exit 2
  fi
done
exec "$TELEOPIT_PYTHON" "$ROOT_DIR/scripts/run/run_sim2real.py" \
  --config-name pico4_sim2real_rh56e2 \
  controller.policy_path=ckpt/track_g1.onnx \
  "real_robot.network_interface=$NETWORK_INTERFACE" \
  "hands.rh56e2.left_host=$LEFT_HAND_IP" "hands.rh56e2.right_host=$RIGHT_HAND_IP" \
  "hands.rh56e2.port=${HAND_PORT:-6000}" \
  "hands.rh56e2.write_enabled=$hand_write" "$@"
