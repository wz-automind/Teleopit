#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export NETWORK_INTERFACE="${NETWORK_INTERFACE:-eth1}"
export LEFT_HAND_IP="${LEFT_HAND_IP:-192.168.123.210}"
export RIGHT_HAND_IP="${RIGHT_HAND_IP:-192.168.123.211}"
export HAND_PORT="${HAND_PORT:-6000}"
args=()
if [[ -n "${PICO_ADVERTISE_IP:-}" ]]; then
  args+=("input.bridge_advertise_ip=$PICO_ADVERTISE_IP")
fi
exec bash "$ROOT_DIR/scripts/run/run_sim2real_rh56e2.sh" "${args[@]}" "$@"
