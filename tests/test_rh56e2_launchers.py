import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run(name, *args, **env):
    with tempfile.TemporaryDirectory() as cwd:
        return subprocess.run(
            ["bash", str(ROOT / "scripts" / name), *args],
            cwd=cwd,
            env={
                **os.environ,
                "TELEOPIT_PYTHON": sys.executable,
                "TELEOPIT_DIR": "/nonexistent/old-project",
                "ENABLE_G1_REAL": "",
                "ENABLE_RH56E2_WRITES": "",
                **env,
            },
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )


def test_stock_sim_launcher_loads_rh56e2_config():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run/run_sim.py"),
            "--config-name",
            "pico4_sim_rh56e2",
            "--cfg",
            "job",
            "num_steps=7",
            "viewers=none",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "num_steps: 7" in result.stdout
    assert "g1_29dof_rh56e2.xml" in result.stdout


def test_real_launcher_requires_g1_interlock_and_defaults_to_hand_read_only():
    denied = run("run/run_sim2real_rh56e2.sh", "--cfg", "job")
    assert denied.returncode != 0
    assert "ENABLE_G1_REAL" in denied.stderr
    result = run(
        "run/run_sim2real_rh56e2.sh",
        "--cfg",
        "job",
        ENABLE_G1_REAL="YES",
        LEFT_HAND_IP="192.0.2.1",
        RIGHT_HAND_IP="192.0.2.2",
        NETWORK_INTERFACE="testnic",
    )
    assert result.returncode == 0, result.stderr
    assert "write_enabled: false" in result.stdout
    assert "network_interface: testnic" in result.stdout


@pytest.mark.parametrize(
    "override",
    [
        "hands.rh56e2={write_enabled:true}",
        "hands={rh56e2:{write_enabled:true}}",
    ],
)
def test_real_launcher_rejects_structured_write_gate_overrides(override):
    result = run(
        "run/run_sim2real_rh56e2.sh",
        override,
        "--cfg",
        "job",
        ENABLE_G1_REAL="YES",
        LEFT_HAND_IP="192.0.2.1",
        RIGHT_HAND_IP="192.0.2.2",
        NETWORK_INTERFACE="testnic",
    )
    assert result.returncode != 0
    assert "ENABLE_RH56E2_WRITES" in result.stderr


def test_real_launcher_write_environment_gate_is_authoritative():
    result = run(
        "run/run_sim2real_rh56e2.sh",
        "--cfg",
        "job",
        ENABLE_G1_REAL="YES",
        ENABLE_RH56E2_WRITES="YES",
        LEFT_HAND_IP="192.0.2.1",
        RIGHT_HAND_IP="192.0.2.2",
        NETWORK_INTERFACE="testnic",
    )
    assert result.returncode == 0, result.stderr
    assert "write_enabled: true" in result.stdout


@pytest.mark.parametrize(
    "address,override,expected",
    [
        ("192.0.2.3", None, "192.0.2.3"),
        ("", None, "null"),
        ("192.0.2.3", "192.0.2.4", "192.0.2.4"),
    ],
)
def test_real_launcher_resolves_advertise_address(address, override, expected):
    args = ["--cfg", "job"]
    if override:
        args.insert(0, "input.bridge_advertise_ip=" + override)
    result = run(
        "run/run_sim2real_rh56e2.sh",
        *args,
        ENABLE_G1_REAL="YES",
        LEFT_HAND_IP="192.0.2.1",
        RIGHT_HAND_IP="192.0.2.2",
        NETWORK_INTERFACE="testnic",
        PICO_ADVERTISE_IP=address,
    )
    assert result.returncode == 0, result.stderr
    assert "bridge_advertise_ip: " + expected in result.stdout
    assert "write_enabled: false" in result.stdout


def test_invalid_sim_option_is_not_ignored():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run/run_sim.py"), "--invalid-option"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
