"""Guarded Modbus TCP driver for Inspire RH56E2 hands.

The wire addresses and six-channel order follow the RH56E2 V1.0.1 manual.
The radians-to-hardware conversion follows Unitree ``xr_teleoperate`` for
Inspire hands: 0 is closed, 1000 is open.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Integral, Real
from pathlib import Path
from typing import Any

import numpy as np
from rh56e2_sdk import RH56E2Hand

from teleopit.runtime.common import cfg_get
from teleopit.sim2real.hands.base import (
    HAND_SIDES,
    HandDevice,
    HandInputMapper,
    HandPoseCommand,
)
from teleopit.sim2real.hands.linkerhand_l6 import GripperMapper
from teleopit.sim2real.hands.pico_landmarks import pico_hand_to_landmarks

logger = logging.getLogger(__name__)

DOF_ORDER = ("pinky", "ring", "middle", "index", "thumb_bend", "thumb_rotation")
JOINT_NAMES = (
    "pinky_proximal_joint",
    "ring_proximal_joint",
    "middle_proximal_joint",
    "index_proximal_joint",
    "thumb_proximal_pitch_joint",
    "thumb_proximal_yaw_joint",
)
RAD_MIN = np.asarray((0.0, 0.0, 0.0, 0.0, 0.0, -0.1), dtype=np.float64)
RAD_MAX = np.asarray((1.7, 1.7, 1.7, 1.7, 0.5, 1.3), dtype=np.float64)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOMEHAND_CONFIG = (
    "assets/rh56e2/somehand/configs/retargeting/bihand/inspire_rh56e2_bihand.yaml"
)


def radians_to_raw(values: Sequence[float]) -> tuple[int, ...]:
    radians = np.asarray(values, dtype=np.float64).reshape(-1)
    if radians.shape != (6,) or not np.all(np.isfinite(radians)):
        raise ValueError("RH56E2 retargeting output must contain six finite radians")
    normalized = np.clip((RAD_MAX - radians) / (RAD_MAX - RAD_MIN), 0.0, 1.0)
    return tuple(int(value) for value in np.rint(normalized * 1000.0))


@dataclass(frozen=True)
class Rh56e2Config:
    mode: str
    sides: tuple[str, ...]
    endpoints: dict[str, tuple[str, int]]
    unit_id: int
    timeout_s: float
    rate_hz: float
    frame_timeout_s: float
    min_change: int
    write_enabled: bool
    max_temperature_c: int
    health_poll_interval_s: float
    open_on_failure: bool
    open_on_shutdown: bool
    open_pose: tuple[int, ...]
    close_pose: tuple[int, ...]
    hold_pose: tuple[int, ...]
    speed: tuple[int, ...]
    trigger_deadzone: float
    deadman_threshold: float
    fixed_thumb_yaw: int | None
    somehand_config_path: str
    somehand_rate_hz: float


def parse_rh56e2_config(cfg: Any) -> Rh56e2Config:
    hands_cfg = cfg_get(cfg, "hands", {}) or {}
    hand_cfg = cfg_get(hands_cfg, "rh56e2", {}) or {}
    somehand_cfg = cfg_get(hands_cfg, "somehand", {}) or {}
    mode = str(cfg_get(hands_cfg, "mode", "vr_hand_pose")).strip().lower()
    if mode not in ("gripper", "vr_hand_pose"):
        raise ValueError(f"hands.mode must be gripper or vr_hand_pose, got {mode!r}")
    sides = tuple(
        str(side).strip().lower() for side in cfg_get(hands_cfg, "sides", HAND_SIDES)
    )
    if (
        not sides
        or len(set(sides)) != len(sides)
        or any(side not in HAND_SIDES for side in sides)
    ):
        raise ValueError("hands.sides must contain unique left, right, or both sides")
    endpoints: dict[str, tuple[str, int]] = {}
    for side in sides:
        host = str(cfg_get(hand_cfg, f"{side}_host", "")).strip()
        if not host:
            raise ValueError(f"hands.rh56e2.{side}_host is required")
        port = _integer(
            cfg_get(hand_cfg, f"{side}_port", cfg_get(hand_cfg, "port", 6000)),
            f"{side}_port",
        )
        if not 1 <= port <= 65535:
            raise ValueError(f"hands.rh56e2.{side}_port must be in 1..65535")
        endpoints[side] = (host, port)
    if len(set(endpoints.values())) != len(endpoints):
        raise ValueError(
            "left and right RH56E2 hands must use distinct IP:port endpoints"
        )
    open_pose = _pose(cfg_get(hand_cfg, "open_pose", [1000] * 6), "open_pose")
    close_pose = _pose(cfg_get(hand_cfg, "close_pose", [0] * 6), "close_pose")
    speed = _pose(cfg_get(hand_cfg, "speed", [200] * 6), "speed")
    fixed_thumb_yaw_value = cfg_get(hand_cfg, "fixed_thumb_yaw", None)
    fixed_thumb_yaw = (
        None
        if fixed_thumb_yaw_value is None
        else _raw_value(fixed_thumb_yaw_value, "fixed_thumb_yaw")
    )
    return Rh56e2Config(
        mode=mode,
        sides=sides,
        endpoints=endpoints,
        unit_id=_u8(cfg_get(hand_cfg, "unit_id", 0xFF), "unit_id"),
        timeout_s=_positive_float(cfg_get(hand_cfg, "timeout_s", 0.5), "timeout_s"),
        rate_hz=_positive_float(cfg_get(hands_cfg, "rate_hz", 30.0), "rate_hz"),
        frame_timeout_s=_positive_float(
            cfg_get(hands_cfg, "frame_timeout_s", 0.25), "frame_timeout_s"
        ),
        min_change=_nonnegative_integer(
            cfg_get(hand_cfg, "min_change", 3), "min_change"
        ),
        write_enabled=_boolean(
            cfg_get(hand_cfg, "write_enabled", False), "write_enabled"
        ),
        max_temperature_c=_temperature_limit(
            cfg_get(hand_cfg, "max_temperature_c", 70)
        ),
        health_poll_interval_s=_positive_float(
            cfg_get(hand_cfg, "health_poll_interval_s", 0.5), "health_poll_interval_s"
        ),
        open_on_failure=_boolean(
            cfg_get(hand_cfg, "open_on_failure", False), "open_on_failure"
        ),
        open_on_shutdown=_boolean(
            cfg_get(hand_cfg, "open_on_shutdown", False), "open_on_shutdown"
        ),
        open_pose=open_pose,
        close_pose=close_pose,
        hold_pose=(-1, -1, -1, -1, -1, -1),
        speed=speed,
        trigger_deadzone=_unit_interval(
            cfg_get(hand_cfg, "trigger_deadzone", 0.05), "trigger_deadzone"
        ),
        deadman_threshold=_unit_interval(
            cfg_get(hand_cfg, "deadman_threshold", 0.5), "deadman_threshold"
        ),
        fixed_thumb_yaw=fixed_thumb_yaw,
        somehand_config_path=str(
            cfg_get(somehand_cfg, "config_path", DEFAULT_SOMEHAND_CONFIG)
        ),
        somehand_rate_hz=_positive_float(
            cfg_get(somehand_cfg, "rate_hz", 60.0), "somehand.rate_hz"
        ),
    )


class Rh56e2Device(HandDevice):
    def __init__(self, config: Rh56e2Config):
        self.config = config
        self._hands: dict[str, RH56E2Hand] = {}
        self._last_pose: dict[str, tuple[int, ...] | None] = {
            side: None for side in config.sides
        }
        self._last_write_s: dict[str, float] = {side: 0.0 for side in config.sides}

    def connect(self) -> None:
        try:
            for side, (host, port) in self.config.endpoints.items():
                hand = RH56E2Hand(
                    host,
                    port,
                    unit_id=self.config.unit_id,
                    timeout=self.config.timeout_s,
                    write_enabled=self.config.write_enabled,
                    max_temperature_c=self.config.max_temperature_c,
                )
                hand.connect()
                self._hands[side] = hand
                telemetry = hand.read_telemetry()
                logger.info(
                    "RH56E2 %s connected at %s:%d; angles=%s",
                    side,
                    host,
                    port,
                    telemetry.angle,
                )
            if self.config.write_enabled:
                for hand in self._hands.values():
                    hand.set_speed(self.config.speed)
            else:
                logger.warning("RH56E2 write interlock is OFF; telemetry is read-only")
        except Exception:
            self.close()
            raise

    def get_state(self, side: str) -> tuple[float, ...]:
        return tuple(float(value) for value in self._hand(side).read_telemetry().angle)

    def send_pose(
        self, side: str, pose: Sequence[int], *, force: bool = False, reason: str = ""
    ) -> None:
        values = RH56E2Hand.validate_positions(pose)
        if not self.config.write_enabled:
            logger.debug("RH56E2 %s dry-run pose=%s reason=%s", side, values, reason)
            return
        now = time.monotonic()
        minimum_interval = 1.0 / self.config.rate_hz
        if not force and now - self._last_write_s[side] < minimum_interval:
            return
        previous = self._last_pose[side]
        if (
            not force
            and previous is not None
            and max(abs(a - b) for a, b in zip(values, previous))
            < self.config.min_change
        ):
            return
        self._hand(side).set_positions(values)
        self._last_pose[side] = values
        self._last_write_s[side] = now

    def open_all(self, *, force: bool = False, reason: str = "") -> None:
        pose = self.config.open_pose
        if reason == "failure" and not self.config.open_on_failure:
            pose = self.config.hold_pose
        for side in self.config.sides:
            self.send_pose(side, pose, force=force, reason=reason)

    def close(self) -> None:
        if self.config.write_enabled and self.config.open_on_shutdown:
            try:
                self.open_all(force=True, reason="shutdown")
            except Exception:
                logger.exception("Failed to open RH56E2 hands during shutdown")
        for hand in self._hands.values():
            hand.close()
        self._hands.clear()

    def diagnostics(self, side: str) -> dict[str, tuple[int, ...]]:
        telemetry = self._hand(side).read_telemetry()
        return {
            "angle": telemetry.angle,
            "force": telemetry.force,
            "current": telemetry.current,
            "fault": telemetry.fault,
            "state": telemetry.state,
            "temperature": telemetry.temperature,
        }

    def _hand(self, side: str) -> RH56E2Hand:
        if side not in self.config.sides:
            raise ValueError(f"RH56E2 side is not configured: {side!r}")
        hand = self._hands.get(side)
        if hand is None:
            raise RuntimeError(f"RH56E2 {side} is not connected")
        return hand


class Rh56e2SomehandMapper(HandInputMapper):
    def __init__(self, config: Rh56e2Config):
        self.config = config
        self._engine: dict[str, Any] = {}
        self._indices: dict[str, np.ndarray] = {}
        self._hand_frame_cls: Any | None = None
        self._next_tick_s = 0.0

    def start(self) -> None:
        from somehand.api import (
            HandFrame,
            RetargetingEngine,
            load_bihand_config,
            load_retargeting_config,
        )

        config_path = Path(self.config.somehand_config_path).expanduser()
        if not config_path.is_absolute():
            config_path = (PROJECT_ROOT / config_path).resolve()
        if not config_path.exists():
            raise FileNotFoundError(f"RH56E2 somehand config not found: {config_path}")
        bihand = load_bihand_config(str(config_path))
        paths = {"left": bihand.left_config_path, "right": bihand.right_config_path}
        self._hand_frame_cls = HandFrame
        for side in self.config.sides:
            engine = RetargetingEngine(load_retargeting_config(paths[side]))
            index = engine.hand_model.get_joint_name_to_qpos_index()
            prefix = "L" if side == "left" else "R"
            names = tuple(f"{prefix}_{name}" for name in JOINT_NAMES)
            try:
                self._indices[side] = np.asarray(
                    [index[name] for name in names], dtype=np.int64
                )
            except KeyError as exc:
                raise ValueError(
                    f"somehand RH56E2 model is missing joint {exc.args[0]!r}"
                ) from exc
            self._engine[side] = engine

    def map(
        self,
        *,
        controller_snapshot: object | None,
        hand_snapshot: object | None,
        active: bool,
        now_s: float,
    ) -> tuple[HandPoseCommand, ...]:
        del controller_snapshot
        if now_s < self._next_tick_s:
            return ()
        self._next_tick_s = now_s + 1.0 / self.config.somehand_rate_hz
        if not active or hand_snapshot is None:
            return self._hold_commands("inactive")
        timestamp_s = float(getattr(hand_snapshot, "timestamp_s", 0.0))
        if now_s - timestamp_s > self.config.frame_timeout_s:
            return self._hold_commands("tracking-timeout")
        commands: list[HandPoseCommand] = []
        for side in self.config.sides:
            state = getattr(hand_snapshot, side, None)
            if (
                state is None
                or not bool(getattr(state, "present", False))
                or not bool(getattr(state, "active", False))
            ):
                commands.append(
                    HandPoseCommand(
                        side, self.config.hold_pose, True, "tracking-missing"
                    )
                )
                continue
            frame = self._hand_frame_cls(
                landmarks_3d=pico_hand_to_landmarks(state.joints),
                landmarks_2d=None,
                hand_side=side,
            )
            result = self._engine[side].process(frame)
            radians = np.asarray(result.qpos, dtype=np.float64).reshape(-1)[
                self._indices[side]
            ]
            commands.append(
                HandPoseCommand(side, radians_to_raw(radians), False, "vr-hand-pose")
            )
        return tuple(commands)

    def close(self) -> None:
        self._engine.clear()
        self._indices.clear()

    def _hold_commands(self, reason: str) -> tuple[HandPoseCommand, ...]:
        return tuple(
            HandPoseCommand(side, self.config.hold_pose, False, reason)
            for side in self.config.sides
        )


def build_rh56e2(cfg: Any) -> tuple[HandDevice, HandInputMapper]:
    config = parse_rh56e2_config(cfg)
    device = Rh56e2Device(config)
    mapper: HandInputMapper
    if config.mode == "vr_hand_pose":
        mapper = Rh56e2SomehandMapper(config)
    else:
        mapper = GripperMapper(config)
    return device, mapper


def _u8(value: object, name: str) -> int:
    parsed = _integer(value, name)
    if not 0 <= parsed <= 0xFF:
        raise ValueError(f"{name} must be in 0..255, got {value!r}")
    return parsed


def _raw_value(value: object, name: str) -> int:
    parsed = _integer(value, name)
    if not 0 <= parsed <= 1000:
        raise ValueError(f"hands.rh56e2.{name} must be in 0..1000, got {value!r}")
    return parsed


def _pose(values: Sequence[object], name: str) -> tuple[int, ...]:
    pose = tuple(_raw_value(value, name) for value in values)
    if len(pose) != 6:
        raise ValueError(f"hands.rh56e2.{name} must contain six values")
    return pose


def _positive_float(value: object, name: str) -> float:
    parsed = _finite_float(value, name)
    if parsed <= 0:
        raise ValueError(f"hands.rh56e2.{name} must be positive, got {value!r}")
    return parsed


def _unit_interval(value: object, name: str) -> float:
    parsed = _finite_float(value, name)
    if not 0.0 <= parsed <= 1.0:
        raise ValueError(f"hands.rh56e2.{name} must be in 0..1, got {value!r}")
    return parsed


def _temperature_limit(value: object) -> int:
    parsed = _integer(value, "max_temperature_c")
    if not 1 <= parsed <= 100:
        raise ValueError(
            f"hands.rh56e2.max_temperature_c must be in 1..100, got {value!r}"
        )
    return parsed


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"hands.rh56e2.{name} must be a boolean, not {value!r}")
    return value


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"hands.rh56e2.{name} must be an integer, not {value!r}")
    return int(value)


def _nonnegative_integer(value: object, name: str) -> int:
    parsed = _integer(value, name)
    if parsed < 0:
        raise ValueError(f"hands.rh56e2.{name} must be nonnegative, got {value!r}")
    return parsed


def _finite_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"hands.rh56e2.{name} must be numeric, not {value!r}")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"hands.rh56e2.{name} must be finite, got {value!r}")
    return parsed
