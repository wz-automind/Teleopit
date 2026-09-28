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
