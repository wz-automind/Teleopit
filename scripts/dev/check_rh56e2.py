#!/usr/bin/env python3
"""Check this fork and optionally read E2 telemetry; never enable writes."""
from __future__ import annotations

import argparse
import importlib
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('sim', 'real'), default='sim')
    parser.add_argument('--hardware', action='store_true')
    parser.add_argument('--left-host')
    parser.add_argument('--right-host')
    parser.add_argument('--port', type=int, default=6000)
    parser.add_argument('--unit-id', type=lambda x: int(x, 0), default=255)
    parser.add_argument('--tactile', action='store_true', help='Read all T1 arrays as well as telemetry')
    args = parser.parse_args()
    if args.hardware and not (args.left_host or args.right_host):
        parser.error('--hardware requires --left-host and/or --right-host')
    if args.tactile and not args.hardware:
        parser.error('--tactile requires --hardware')
    if args.left_host and args.left_host == args.right_host:
        parser.error('Hand endpoints must be different')
    errors = []
    modules = ['teleopit', 'rh56e2_sdk', 'somehand.api', 'pico_bridge', 'mujoco', 'onnxruntime', 'hydra']
    if args.profile == 'real':
        modules.append('g1_bridge_sdk')
    for name in modules:
        try:
            module = importlib.import_module(name)
            if name == 'teleopit' and Path(module.__file__).resolve().parent != ROOT / 'teleopit':
                raise RuntimeError('wrong Teleopit checkout: ' + str(module.__file__))
            print('OK import', name)
        except Exception as exc:
            errors.append(f'{name}: {exc}')
    for name, expected in [('rh56e2-sdk', '0.1.0'), ('somehand', '0.3.0'), ('pico-bridge', '0.2.1')]:
        try:
            actual = version(name)
            if actual != expected:
                errors.append(f'{name}: expected {expected}, got {actual}')
        except Exception as exc:
            errors.append(f'{name}: {exc}')
    for relative in ['ckpt/track_g1.onnx', 'assets/robots/unitree_g1/g1_29dof_rh56e2.xml',
                     'assets/rh56e2/somehand/configs/retargeting/bihand/inspire_rh56e2_bihand.yaml']:
        if not (ROOT / relative).is_file():
            errors.append('Missing resource: ' + relative)
    if args.hardware and not errors:
        from rh56e2_sdk import RH56E2Hand
        for host in filter(None, (args.left_host, args.right_host)):
            try:
                with RH56E2Hand(host, args.port, unit_id=args.unit_id, timeout=2) as hand:
                    telemetry = hand.read_telemetry()
                    print(host, telemetry)
                    if any(telemetry.fault) or max(telemetry.temperature) > 70:
                        errors.append(f'{host}: fault or temperature check failed')
                    if args.tactile:
                        frame = hand.read_tactile_all()
                        print(host, 'T1 regions:', len(frame), 'cells:', sum(len(s.values) for s in frame.values()))
            except Exception as exc:
                errors.append(f'{host}: {exc}')
    for error in errors:
        print('FAIL', error)
    print('No device writes performed. These checks do not certify motion safety.')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
