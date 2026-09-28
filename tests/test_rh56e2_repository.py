import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_e2_integration_has_one_user_guide_and_no_migration_tooling():
    removed = (
        "MIGRATION.md",
        "docs/zh/assets.md",
        "docs/zh/deployment.md",
        "docs/superpowers/plans/2026-09-27-teleopit-deployment-fixes.md",
        "scripts/dev/validate.sh",
        "scripts/run/run_sim_rh56e2.py",
        "scripts/run/run_sim_rh56e2.sh",
        "scripts/run/run_unitree_g1_rh56e2.sh",
        "scripts/setup/install_rh56e2.sh",
        "scripts/setup/package_rh56e2.py",
        "teleopit/sim2real/hands/rh56e2_protocol.py",
        "teleopit/pipeline_rh56e2.py",
        "teleopit/robots/mujoco_robot_rh56e2.py",
        "teleopit/sim/loop_rh56e2.py",
        "teleopit/sim/session_rh56e2.py",
        "tests/test_rh56e2_bundle.py",
    )
    assert not [path for path in removed if (ROOT / path).exists()]

    guide = (ROOT / "docs/zh/usage.md").read_text()
    assert "run_sim.py --config-name pico4_sim_rh56e2" in guide
    assert "run_sim2real_rh56e2.sh" in guide
    assert "scp" in guide
    assert "6000" in guide


def test_e2_tests_skip_cleanly_without_private_sdk(tmp_path):
    (tmp_path / "sitecustomize.py").write_text(
        """
import importlib.abc
import sys

class BlockPrivateSdk(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "rh56e2_sdk" or fullname.startswith("rh56e2_sdk."):
            raise ModuleNotFoundError("private SDK intentionally unavailable")

sys.meta_path.insert(0, BlockPrivateSdk())
"""
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(tmp_path), str(ROOT), env.get("PYTHONPATH", "")]
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_rh56e2_config.py",
            "tests/test_rh56e2_integration.py",
            "tests/test_rh56e2_resources.py",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
