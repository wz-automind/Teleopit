import os
import tempfile
from pathlib import Path

import mujoco
import pytest


def require_file(path: Path) -> Path:
    if not path.is_file():
        pytest.skip(f"optional RH56E2 resource is not installed: {path}")
    return path


def test_retargeting_resources_load_outside_repo():
    pytest.importorskip("rh56e2_sdk", reason="private RH56E2 SDK is not installed")
    pytest.importorskip("somehand.api", reason="optional somehand is not installed")
    from somehand.api import load_bihand_config, load_retargeting_config

    from teleopit.sim2real.hands.rh56e2 import (
        DEFAULT_SOMEHAND_CONFIG,
        JOINT_NAMES,
        PROJECT_ROOT,
    )

    model_root = PROJECT_ROOT / "assets/rh56e2/somehand/assets/mjcf"
    if not all(
        (model_root / name / "model.xml").is_file()
        for name in ("inspire_rh56e2_left", "inspire_rh56e2_right")
    ):
        pytest.skip("optional RH56E2 hand models are not installed")

    original = Path.cwd()
    try:
        with tempfile.TemporaryDirectory() as folder:
            os.chdir(folder)
            bihand = load_bihand_config(str(PROJECT_ROOT / DEFAULT_SOMEHAND_CONFIG))
            for prefix, path in [
                ("L", bihand.left_config_path),
                ("R", bihand.right_config_path),
            ]:
                cfg = load_retargeting_config(path)
                model_path = require_file(Path(cfg.hand.mjcf_path))
                assert model_path.is_relative_to(
                    PROJECT_ROOT / "assets/rh56e2/somehand"
                )
                model = mujoco.MjModel.from_xml_path(str(model_path))
                for name in JOINT_NAMES:
                    assert model.joint(prefix + "_" + name).id >= 0
    finally:
        os.chdir(original)


def test_g1_e2_model_advances_finite_physics():
    import numpy as np

    root = Path(__file__).resolve().parents[1]
    model = mujoco.MjModel.from_xml_path(
        str(require_file(root / "assets/robots/unitree_g1/g1_29dof_rh56e2.xml"))
    )
    data = mujoco.MjData(model)
    for _ in range(20):
        mujoco.mj_step(model, data)
    assert np.isfinite(data.qpos).all()
    assert data.time > 0


def test_stock_mujoco_robot_reads_only_policy_joints(tmp_path):
    import numpy as np
    from omegaconf import OmegaConf

    from teleopit.robots.mujoco_robot import MuJoCoRobot

    xml_path = tmp_path / "robot.xml"
    xml_path.write_text(
        """
<mujoco>
  <worldbody>
    <body name="base" pos="0 0 1">
      <freejoint/>
      <geom type="sphere" size="0.05" mass="1"/>
      <body name="policy_link_0">
        <joint name="policy_0" type="hinge" axis="1 0 0"/>
        <geom type="sphere" size="0.03" mass="0.1"/>
        <body name="hand_link">
          <joint name="extra_hand" type="hinge" axis="0 1 0"/>
          <geom type="sphere" size="0.02" mass="0.1"/>
          <body name="policy_link_1">
            <joint name="policy_1" type="hinge" axis="0 0 1"/>
            <geom type="sphere" size="0.01" mass="0.1"/>
          </body>
        </body>
      </body>
    </body>
  </worldbody>
  <actuator>
    <motor joint="policy_0"/>
    <motor joint="policy_1"/>
    <motor joint="extra_hand"/>
  </actuator>
</mujoco>
"""
    )
    cfg = OmegaConf.create(
        {
            "xml_path": str(xml_path),
            "num_actions": 2,
            "kps": [10, 10],
            "kds": [1, 1],
            "default_angles": [0.1, -0.2],
            "torque_limits": [5, 5],
            "builtin_pd": False,
            "action_scale": 1.0,
            "mujoco_default_qpos": [0, 0, 1, 1, 0, 0, 0, 0.1, -0.2],
        }
    )
    robot = MuJoCoRobot(cfg)
    expected_qpos = []
    expected_qvel = []
    for actuator_id in range(cfg.num_actions):
        joint_id = int(robot.model.actuator_trnid[actuator_id][0])
        expected_qpos.append(int(robot.model.jnt_qposadr[joint_id]))
        expected_qvel.append(int(robot.model.jnt_dofadr[joint_id]))

    robot.data.qpos[:] = np.arange(robot.model.nq)
    robot.data.qvel[:] = np.arange(robot.model.nv) + 100
    state = robot.get_state()
    np.testing.assert_array_equal(state.qpos, robot.data.qpos[expected_qpos])
    np.testing.assert_array_equal(state.qvel, robot.data.qvel[expected_qvel])

    compact = np.asarray([0, 0, 1, 1, 0, 0, 0, 0.25, -0.25], dtype=np.float64)
    robot.reset(compact)
    np.testing.assert_array_equal(robot.data.qpos[:7], compact[:7])
    np.testing.assert_array_equal(robot.data.qpos[expected_qpos], compact[7:])


def test_sim_hands_resolve_resources_outside_repo():
    pytest.importorskip("somehand.api", reason="optional somehand is not installed")
    from types import SimpleNamespace

    from teleopit.sim.rh56e2_hands import Rh56e2SimHands

    root = Path(__file__).resolve().parents[1]
    model = mujoco.MjModel.from_xml_path(
        str(require_file(root / "assets/robots/unitree_g1/g1_29dof_rh56e2.xml"))
    )
    original = Path.cwd()
    try:
        with tempfile.TemporaryDirectory() as folder:
            os.chdir(folder)
            hands = Rh56e2SimHands(SimpleNamespace(model=model), object(), {})
            assert len(hands._la) == 6
            assert len(hands._ra) == 6
    finally:
        os.chdir(original)
