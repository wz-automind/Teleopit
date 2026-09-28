#!/usr/bin/env python3
"""Run Pico-driven RH56E2 hands in a standalone MuJoCo window."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path(
    "assets/rh56e2/somehand/configs/retargeting/bihand/"
    "inspire_rh56e2_bihand.yaml"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pico-driven two-hand RH56E2 MuJoCo viewer"
    )
    parser.add_argument(
        "--config",
        help="somehand bihand configuration (default: repository RH56E2 config)",
    )
    parser.add_argument("--bridge-host", default="0.0.0.0")
    parser.add_argument("--bridge-port", type=int, default=63901)
    parser.add_argument("--bridge-advertise-ip")
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="seconds to wait for the first Pico hand packet",
    )
    parser.add_argument("--bridge-start-timeout", type=float, default=10.0)
    return parser


def resolve_config_path(raw: str | Path | None) -> Path:
    path = PROJECT_ROOT / DEFAULT_CONFIG if raw is None else Path(raw).expanduser()
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"RH56E2 bihand config not found: {path}")
    return path


def build_runtime(
    args: argparse.Namespace,
    *,
    provider_cls: type[Any] | None = None,
    engine_cls: type[Any] | None = None,
    sink_cls: type[Any] | None = None,
) -> Any:
    from teleopit.sim.rh56e2_standalone import Rh56e2StandaloneRuntime

    if provider_cls is None:
        from teleopit.inputs.pico4_provider import Pico4InputProvider

        provider_cls = Pico4InputProvider
    if engine_cls is None:
        from somehand.api import BiHandRetargetingEngine

        engine_cls = BiHandRetargetingEngine
    if sink_cls is None:
        from somehand.runtime import BiHandOutputWindowSink

        sink_cls = BiHandOutputWindowSink

    config_path = resolve_config_path(args.config)
    engine = engine_cls.from_config_path(str(config_path))
    provider = provider_cls(
        timeout=args.timeout,
        pause_button=None,
        arms_button=None,
        bridge_host=args.bridge_host,
        bridge_port=args.bridge_port,
        bridge_advertise_ip=args.bridge_advertise_ip,
        bridge_video_enabled=False,
        bridge_start_timeout=args.bridge_start_timeout,
    )
    try:
        sink = sink_cls(
            engine.left_engine.hand_model,
            engine.right_engine.hand_model,
        )
    except BaseException:
        provider.close()
        raise

    return Rh56e2StandaloneRuntime(
        provider,
        engine,
        sink,
        first_frame_timeout_s=args.timeout,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runtime = build_runtime(args)
    print("RH56E2 standalone simulation")
    print(f"Pico Bridge: {args.bridge_host}:{args.bridge_port}")
    print("Waiting for Pico hand tracking; close the window or press Ctrl+C to stop.")
    processed = runtime.run()
    print(f"Stopped after {processed} hand frames.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
