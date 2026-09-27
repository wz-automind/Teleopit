from __future__ import annotations

import struct
import unittest

from teleopit.sim2real.hands.rh56e2 import (  # noqa: E402
    parse_rh56e2_config,
    radians_to_raw,
)
from teleopit.sim2real.hands.rh56e2_protocol import (  # noqa: E402
    ModbusProtocolError,
    build_read_frame,
    build_write_frame,
    parse_read_response,
    parse_write_response,
)


def response(pdu: bytes, *, transaction_id: int = 9, unit_id: int = 0xFF) -> bytes:
    return struct.pack(">HHHB", transaction_id, 0, len(pdu) + 1, unit_id) + pdu


class ProtocolTests(unittest.TestCase):
    def test_build_read_frame(self) -> None:
        self.assertEqual(
            build_read_frame(1, 0xFF, 1546, 6).hex(),
            "000100000006ff03060a0006",
        )

    def test_build_write_frame_encodes_hold_as_ffff(self) -> None:
        frame = build_write_frame(2, 0xFF, 1486, [0, 1, 500, 999, 1000, -1])
        self.assertEqual(frame[:7].hex(), "000200000013ff")
        self.assertEqual(frame[7:13].hex(), "1005ce00060c")
        self.assertEqual(frame[13:].hex(), "0000000101f403e703e8ffff")

    def test_parse_read_response(self) -> None:
        frame = response(b"\x03\x0c" + struct.pack(">6H", 0, 1, 500, 999, 1000, 65535))
        self.assertEqual(parse_read_response(frame, count=6), (0, 1, 500, 999, 1000, 65535))

    def test_parse_write_response_ignores_transaction_id_quirk(self) -> None:
        frame = response(struct.pack(">BHH", 0x10, 1486, 6), transaction_id=77)
        parse_write_response(frame, address=1486, count=6)

    def test_modbus_exception_is_rejected(self) -> None:
        with self.assertRaises(ModbusProtocolError):
            parse_read_response(response(b"\x83\x02"), count=6)


class MappingTests(unittest.TestCase):
    def test_unitree_inspire_ranges_map_open_to_1000(self) -> None:
        self.assertEqual(radians_to_raw([0, 0, 0, 0, 0, -0.1]), (1000,) * 6)

    def test_unitree_inspire_ranges_map_closed_to_zero(self) -> None:
        self.assertEqual(radians_to_raw([1.7, 1.7, 1.7, 1.7, 0.5, 1.3]), (0,) * 6)


class ConfigTests(unittest.TestCase):
    def test_false_like_gate_values_are_rejected_before_runtime(self) -> None:
        from omegaconf import OmegaConf
        for gate in ('write_enabled', 'open_on_failure', 'open_on_shutdown'):
            for value in ('false', '0', 'true', 0, 1):
                cfg = OmegaConf.create({'hands': {'sides': ['left'], 'rh56e2': {'left_host': 'test', gate: value}}})
                with self.subTest(gate=gate, value=value), self.assertRaises((TypeError, ValueError)):
                    parse_rh56e2_config(cfg)
            for value in (False, True):
                cfg = OmegaConf.create({'hands': {'sides': ['left'], 'rh56e2': {'left_host': 'test', gate: value}}})
                self.assertIs(getattr(parse_rh56e2_config(cfg), gate), value)

    def test_nonfinite_timing_and_invalid_numeric_types_are_rejected(self) -> None:
        from omegaconf import OmegaConf
        paths = ('hands.rate_hz', 'hands.frame_timeout_s', 'hands.rh56e2.timeout_s',
                 'hands.rh56e2.health_poll_interval_s', 'hands.somehand.rate_hz')
        for path in paths:
            for value in (float('nan'), float('inf'), -float('inf'), 0, -1, True, '1'):
                cfg = OmegaConf.create({'hands': {'sides': ['left'], 'rh56e2': {'left_host': 'test'}}})
                OmegaConf.update(cfg, path, value)
                with self.subTest(path=path, value=value), self.assertRaises((TypeError, ValueError)):
                    parse_rh56e2_config(cfg)

    def test_integer_settings_never_truncate_or_coerce(self) -> None:
        fields = ('port', 'left_port', 'unit_id', 'min_change', 'max_temperature_c', 'fixed_thumb_yaw')
        for field in fields:
            for value in (True, 1.5, '25'):
                cfg = {'hands': {'sides': ['left'], 'rh56e2': {'left_host': 'test', field: value}}}
                with self.subTest(field=field, value=value), self.assertRaises((TypeError, ValueError)):
                    parse_rh56e2_config(cfg)
        for field in ('open_pose', 'close_pose', 'speed'):
            for value in (True, 250.5, '250'):
                cfg = {'hands': {'sides': ['left'], 'rh56e2': {'left_host': 'test', field: [value] * 6}}}
                with self.subTest(field=field, value=value), self.assertRaises((TypeError, ValueError)):
                    parse_rh56e2_config(cfg)

    def test_writes_are_disabled_by_default(self) -> None:
        cfg = {
            "hands": {
                "sides": ["left"],
                "rh56e2": {"left_host": "192.168.11.210"},
            }
        }
        parsed = parse_rh56e2_config(cfg)
        self.assertFalse(parsed.write_enabled)
        self.assertEqual(parsed.endpoints["left"], ("192.168.11.210", 6000))

    def test_dual_hands_cannot_share_one_endpoint(self) -> None:
        cfg = {
            "hands": {
                "sides": ["left", "right"],
                "rh56e2": {
                    "left_host": "192.168.11.210",
                    "right_host": "192.168.11.210",
                },
            }
        }
        with self.assertRaisesRegex(ValueError, "distinct"):
            parse_rh56e2_config(cfg)


if __name__ == "__main__":
    unittest.main()
