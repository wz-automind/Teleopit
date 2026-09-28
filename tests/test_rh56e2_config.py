from __future__ import annotations

import unittest

from teleopit.sim2real.hands.rh56e2 import (
    parse_rh56e2_config,
    radians_to_raw,
)


class MappingTests(unittest.TestCase):
    def test_unitree_inspire_ranges_map_open_to_1000(self) -> None:
        self.assertEqual(radians_to_raw([0, 0, 0, 0, 0, -0.1]), (1000,) * 6)

    def test_unitree_inspire_ranges_map_closed_to_zero(self) -> None:
        self.assertEqual(radians_to_raw([1.7, 1.7, 1.7, 1.7, 0.5, 1.3]), (0,) * 6)


class ConfigTests(unittest.TestCase):
    def test_false_like_gate_values_are_rejected_before_runtime(self) -> None:
        from omegaconf import OmegaConf

        for gate in ("write_enabled", "open_on_failure", "open_on_shutdown"):
            for value in ("false", "0", "true", 0, 1):
                cfg = OmegaConf.create(
                    {
                        "hands": {
                            "sides": ["left"],
                            "rh56e2": {"left_host": "test", gate: value},
                        }
                    }
                )
                with (
                    self.subTest(gate=gate, value=value),
                    self.assertRaises((TypeError, ValueError)),
                ):
                    parse_rh56e2_config(cfg)
            for value in (False, True):
                cfg = OmegaConf.create(
                    {
                        "hands": {
                            "sides": ["left"],
                            "rh56e2": {"left_host": "test", gate: value},
                        }
                    }
                )
                self.assertIs(getattr(parse_rh56e2_config(cfg), gate), value)

    def test_nonfinite_timing_and_invalid_numeric_types_are_rejected(self) -> None:
        from omegaconf import OmegaConf

        paths = (
            "hands.rate_hz",
            "hands.frame_timeout_s",
            "hands.rh56e2.timeout_s",
            "hands.rh56e2.health_poll_interval_s",
            "hands.somehand.rate_hz",
        )
        for path in paths:
            for value in (float("nan"), float("inf"), -float("inf"), 0, -1, True, "1"):
                cfg = OmegaConf.create(
                    {"hands": {"sides": ["left"], "rh56e2": {"left_host": "test"}}}
                )
                OmegaConf.update(cfg, path, value)
                with (
                    self.subTest(path=path, value=value),
                    self.assertRaises((TypeError, ValueError)),
                ):
                    parse_rh56e2_config(cfg)

    def test_integer_settings_never_truncate_or_coerce(self) -> None:
        fields = (
            "port",
            "left_port",
            "unit_id",
            "min_change",
            "max_temperature_c",
            "fixed_thumb_yaw",
        )
        for field in fields:
            for value in (True, 1.5, "25"):
                cfg = {
                    "hands": {
                        "sides": ["left"],
                        "rh56e2": {"left_host": "test", field: value},
                    }
                }
                with (
                    self.subTest(field=field, value=value),
                    self.assertRaises((TypeError, ValueError)),
                ):
                    parse_rh56e2_config(cfg)
        for field in ("open_pose", "close_pose", "speed"):
            for value in (True, 250.5, "250"):
                cfg = {
                    "hands": {
                        "sides": ["left"],
                        "rh56e2": {"left_host": "test", field: [value] * 6},
                    }
                }
                with (
                    self.subTest(field=field, value=value),
                    self.assertRaises((TypeError, ValueError)),
                ):
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
