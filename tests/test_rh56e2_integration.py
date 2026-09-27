from __future__ import annotations

import importlib
import sys
import time
import unittest
import warnings
from unittest.mock import patch


class LegacyProtocolCompatibilityTests(unittest.TestCase):
    def test_supported_sdk_surface_does_not_export_raw_write_client(self) -> None:
        import rh56e2_sdk as sdk

        self.assertIn("RH56E2Hand", sdk.__all__)
        self.assertNotIn("RH56E2ModbusClient", sdk.__all__)
        self.assertFalse(hasattr(sdk, "RH56E2ModbusClient"))

    def test_legacy_protocol_exports_sdk_objects_and_warns(self) -> None:
        module_name = "teleopit.sim2real.hands.rh56e2_protocol"
        sys.modules.pop(module_name, None)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            legacy = importlib.import_module(module_name)

        from rh56e2_sdk import protocol as sdk_protocol
        from rh56e2_sdk.models import ModbusProtocolError

        self.assertTrue(any(item.category is DeprecationWarning for item in caught))
        self.assertIs(legacy.Rh56e2ModbusClient, sdk_protocol.RH56E2ModbusClient)
        self.assertIs(legacy.ModbusProtocolError, ModbusProtocolError)
        for name in (
            "ANGLE_SET",
            "SPEED_SET",
            "ANGLE_ACT",
            "FORCE_ACT",
            "CURRENT_ACT",
            "FAULT_ACT",
            "STATE_ACT",
            "TEMPERATURE_ACT",
            "build_read_frame",
            "build_write_frame",
            "parse_read_response",
            "parse_write_response",
        ):
            self.assertIs(getattr(legacy, name), getattr(sdk_protocol, name))

    def test_legacy_client_accepts_deprecated_timeout_s_keyword_and_property(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            legacy = importlib.import_module("teleopit.sim2real.hands.rh56e2_protocol")
            Rh56e2ModbusClient = legacy.Rh56e2ModbusClient
            client = Rh56e2ModbusClient("192.0.2.10", timeout_s=0.25)
            self.assertEqual(client.timeout_s, 0.25)

        self.assertEqual(client.timeout, 0.25)
        self.assertTrue(any(item.category is DeprecationWarning for item in caught))


class TeleopitDelegationTests(unittest.TestCase):
    def test_disabled_hands_do_not_require_optional_sdk(self):
        import subprocess
        code = '''
import sys, importlib.abc
class BlockSdk(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.startswith('rh56e2_sdk'):
            raise ModuleNotFoundError('optional SDK unavailable')
sys.meta_path.insert(0, BlockSdk())
from teleopit.sim2real.hands.worker import build_hand_runtime
assert not build_hand_runtime({'hands': {'enabled': False}}).enabled
'''
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_real_sdk_blocks_faults_and_overtemperature_and_preserves_hold(self):
        from rh56e2_sdk import DeviceSafetyError, RH56E2Hand
        from rh56e2_sdk.protocol import FAULT_ACT

        from teleopit.sim2real.hands.rh56e2 import Rh56e2Device, parse_rh56e2_config
        class Device:
            fault = 0
            temperature = 25
            writes = []
            def connect(self): pass
            def close(self): pass
            def read_bytes(self, address, count):
                return bytes([self.fault if address == FAULT_ACT else self.temperature] * count)
            def write_holding(self, address, command):
                self.writes.append((address, command))
        raw = Device()
        hand = RH56E2Hand('test', client=raw, write_enabled=True)
        hand.connect()
        cfg = parse_rh56e2_config({'hands': {'sides': ['left'], 'rh56e2': {'left_host': 'test', 'write_enabled': True}}})
        device = Rh56e2Device(cfg)
        device._hands['left'] = hand
        for fault, temperature in [(1,25), (0,71)]:
            raw.fault, raw.temperature = fault, temperature
            with self.assertRaises(DeviceSafetyError):
                device.send_pose('left', (-1,) * 6, force=True)
        self.assertEqual(raw.writes, [])
        raw.temperature = 25
        device.send_pose('left', (-1,) * 6, force=True)
        self.assertEqual(raw.writes, [(1486, (-1,) * 6)])

    def test_tracking_timeout_holds_without_engine_call(self):
        from types import SimpleNamespace

        from teleopit.sim2real.hands.rh56e2 import (
            Rh56e2SomehandMapper,
            parse_rh56e2_config,
        )
        cfg = parse_rh56e2_config({'hands': {'sides': ['left'], 'rh56e2': {'left_host': 'test'}}})
        mapper = Rh56e2SomehandMapper(cfg)
        commands = mapper.map(controller_snapshot=None, hand_snapshot=SimpleNamespace(timestamp_s=1), active=True, now_s=2)
        self.assertEqual(commands[0].pose, (-1,) * 6)
        self.assertEqual(commands[0].reason, 'tracking-timeout')

    @staticmethod
    def _device(*, write_enabled: bool):
        from teleopit.sim2real.hands.rh56e2 import Rh56e2Device, parse_rh56e2_config

        config = parse_rh56e2_config(
            {
                "hands": {
                    "sides": ["left"],
                    "rh56e2": {"left_host": "192.168.11.210", "write_enabled": write_enabled},
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

        hand_class.return_value.set_positions.assert_called_once_with((100, 200, 300, 400, 500, 600))

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
