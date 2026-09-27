"""Deprecated RH56E2 protocol compatibility imports.

Use :mod:`rh56e2_sdk` for new integrations.
"""

from __future__ import annotations

import warnings

from rh56e2_sdk.models import ModbusProtocolError
from rh56e2_sdk.protocol import (
    ANGLE_ACT,
    ANGLE_SET,
    CURRENT_ACT,
    FAULT_ACT,
    FORCE_ACT,
    SPEED_SET,
    STATE_ACT,
    TEMPERATURE_ACT,
    RH56E2ModbusClient,
    build_read_frame,
    build_write_frame,
    parse_read_response,
    parse_write_response,
)

warnings.warn(
    "teleopit.sim2real.hands.rh56e2_protocol is deprecated; use rh56e2_sdk instead",
    DeprecationWarning,
    stacklevel=2,
)

Rh56e2ModbusClient = RH56E2ModbusClient

__all__ = [
    "ANGLE_SET",
    "SPEED_SET",
    "ANGLE_ACT",
    "FORCE_ACT",
    "CURRENT_ACT",
    "FAULT_ACT",
    "STATE_ACT",
    "TEMPERATURE_ACT",
    "ModbusProtocolError",
    "Rh56e2ModbusClient",
    "build_read_frame",
    "build_write_frame",
    "parse_read_response",
    "parse_write_response",
]
