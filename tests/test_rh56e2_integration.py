from __future__ import annotations

import sys
import time
import unittest
from unittest.mock import patch


class TeleopitDelegationTests(unittest.TestCase):
    def test_simulation_cfg_preserves_optional_hand_section(self):
        from teleopit.runtime.factory import build_simulation_cfg

        sim_hands = {"enabled": True, "config": "e2.yaml"}
        self.assertEqual(
            build_simulation_cfg({"sim_hands": sim_hands})["sim_hands"],
            sim_hands,
        )

    def test_sim_session_builds_hands_only_when_enabled(self):
        from types import SimpleNamespace

        from teleopit.sim.session import _build_sim_hands

        provider = object()
        disabled = SimpleNamespace(
            cfg={"sim_hands": {"enabled": False}},
            robot=object(),
            _try_get_cfg=lambda path, default=None: False,
        )
        self.assertIsNone(_build_sim_hands(disabled, provider))

        enabled = SimpleNamespace(
            cfg={"sim_hands": {"enabled": True}},
            robot=object(),
            _try_get_cfg=lambda path, default=None: True,
        )
        sentinel = object()
        with patch(
            "teleopit.sim.rh56e2_hands.Rh56e2SimHands", return_value=sentinel
        ) as factory:
            self.assertIs(_build_sim_hands(enabled, provider), sentinel)
        factory.assert_called_once_with(
            robot=enabled.robot, input_provider=provider, cfg=enabled.cfg
        )

    def test_disabled_hands_do_not_require_optional_sdk(self):
        import subprocess

        code = """
import sys, importlib.abc
class BlockSdk(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.startswith('rh56e2_sdk'):
            raise ModuleNotFoundError('optional SDK unavailable')
sys.meta_path.insert(0, BlockSdk())
from teleopit.sim2real.hands.worker import build_hand_runtime
assert not build_hand_runtime({'hands': {'enabled': False}}).enabled
"""
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_real_sdk_blocks_faults_and_overtemperature_and_preserves_hold(self):
        from rh56e2_sdk import DeviceSafetyError, RH56E2Hand
        from rh56e2_sdk.protocol import FAULT_ACT

        from teleopit.sim2real.hands.rh56e2 import Rh56e2Device, parse_rh56e2_config

        class Device:
            fault = 0
            temperature = 25

            def __init__(self):
                self.writes = []

            def connect(self):
                pass

            def close(self):
                pass

            def read_bytes(self, address, count):
                return bytes(
                    [self.fault if address == FAULT_ACT else self.temperature] * count
                )

            def write_holding(self, address, command):
                self.writes.append((address, command))

        raw = Device()
        hand = RH56E2Hand("test", client=raw, write_enabled=True)
        hand.connect()
        cfg = parse_rh56e2_config(
            {
                "hands": {
                    "sides": ["left"],
                    "rh56e2": {"left_host": "test", "write_enabled": True},
                }
            }
        )
        device = Rh56e2Device(cfg)
        device._hands["left"] = hand
        for fault, temperature in [(1, 25), (0, 71)]:
            raw.fault, raw.temperature = fault, temperature
            with self.assertRaises(DeviceSafetyError):
                device.send_pose("left", (-1,) * 6, force=True)
        self.assertEqual(raw.writes, [])
        raw.temperature = 25
        device.send_pose("left", (-1,) * 6, force=True)
        self.assertEqual(raw.writes, [(1486, (-1,) * 6)])

    def test_tracking_timeout_holds_without_engine_call(self):
        from types import SimpleNamespace

        from teleopit.sim2real.hands.rh56e2 import (
            Rh56e2SomehandMapper,
            parse_rh56e2_config,
        )

        cfg = parse_rh56e2_config(
            {"hands": {"sides": ["left"], "rh56e2": {"left_host": "test"}}}
        )
        mapper = Rh56e2SomehandMapper(cfg)
        commands = mapper.map(
            controller_snapshot=None,
            hand_snapshot=SimpleNamespace(timestamp_s=1),
            active=True,
            now_s=2,
        )
        self.assertEqual(commands[0].pose, (-1,) * 6)
        self.assertEqual(commands[0].reason, "tracking-timeout")

    @staticmethod
    def _device(*, write_enabled: bool):
        from teleopit.sim2real.hands.rh56e2 import Rh56e2Device, parse_rh56e2_config

        config = parse_rh56e2_config(
            {
                "hands": {
                    "sides": ["left"],
                    "rh56e2": {
                        "left_host": "192.168.11.210",
                        "write_enabled": write_enabled,
                    },
                }
            }
        )
        return Rh56e2Device(config)

    def test_send_pose_delegates_to_sdk_hand_positions(self) -> None:
        from rh56e2_sdk import RH56E2Telemetry

        from teleopit.sim2real.hands.rh56e2 import Rh56e2Device, parse_rh56e2_config

        config = parse_rh56e2_config(
            {
                "hands": {
                    "sides": ["left"],
                    "rh56e2": {"left_host": "192.168.11.210", "write_enabled": True},
                }
            }
        )
        telemetry = RH56E2Telemetry(
            angle=(0, 0, 0, 0, 0, 0),
            force=(0, 0, 0, 0, 0, 0),
            current=(0, 0, 0, 0, 0, 0),
            fault=(0, 0, 0, 0, 0, 0),
            state=(0, 0, 0, 0, 0, 0),
            temperature=(25, 25, 25, 25, 25, 25),
        )
        with patch("teleopit.sim2real.hands.rh56e2.RH56E2Hand") as hand_class:
            hand_class.validate_positions.side_effect = tuple
            hand_class.return_value.read_telemetry.return_value = telemetry
            device = Rh56e2Device(config)
            device.connect()
            device.send_pose("left", (100, 200, 300, 400, 500, 600), force=True)

        hand_class.return_value.set_positions.assert_called_once_with(
            (100, 200, 300, 400, 500, 600)
        )

    def test_invalid_pose_is_rejected_even_when_writes_are_disabled(self) -> None:
        device = self._device(write_enabled=False)

        with self.assertRaises(TypeError):
            device.send_pose("left", (500.5,) * 6)

    def test_invalid_pose_is_rejected_before_rate_limit_suppression(self) -> None:
        device = self._device(write_enabled=True)
        device._last_write_s["left"] = time.monotonic()

        with self.assertRaises(TypeError):
            device.send_pose("left", (500.5,) * 6)

    def test_invalid_pose_is_rejected_before_minimum_change_suppression(self) -> None:
        device = self._device(write_enabled=True)
        device._last_pose["left"] = (500,) * 6

        with self.assertRaises(TypeError):
            device.send_pose("left", (500.5,) * 6)


if __name__ == "__main__":
    unittest.main()
