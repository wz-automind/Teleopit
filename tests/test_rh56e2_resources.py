import os
import tempfile
from pathlib import Path

import mujoco


def test_retargeting_resources_load_outside_repo():
    from somehand.api import load_bihand_config, load_retargeting_config

    from teleopit.sim2real.hands.rh56e2 import (
        DEFAULT_SOMEHAND_CONFIG,
        JOINT_NAMES,
        PROJECT_ROOT,
    )

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
                model_path = Path(cfg.hand.mjcf_path)
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
        str(root / "assets/robots/unitree_g1/g1_29dof_rh56e2.xml")
    )
    data = mujoco.MjData(model)
    for _ in range(20):
        mujoco.mj_step(model, data)
    assert np.isfinite(data.qpos).all()
    assert data.time > 0


def test_stock_mujoco_robot_reads_only_g1_policy_joints():
    import numpy as np
    from omegaconf import OmegaConf

    from teleopit.robots.mujoco_robot import MuJoCoRobot

    root = Path(__file__).resolve().parents[1]
    cfg = OmegaConf.load(root / "teleopit/configs/robot/g1_rh56e2.yaml")
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

    compact = np.arange(7 + cfg.num_actions, dtype=np.float64)
    robot.reset(compact)
    np.testing.assert_array_equal(robot.data.qpos[:7], compact[:7])
    np.testing.assert_array_equal(robot.data.qpos[expected_qpos], compact[7:])


def test_sim_hands_resolve_resources_outside_repo():
    from types import SimpleNamespace

    from teleopit.sim.rh56e2_hands import Rh56e2SimHands

    root = Path(__file__).resolve().parents[1]
    model = mujoco.MjModel.from_xml_path(
        str(root / "assets/robots/unitree_g1/g1_29dof_rh56e2.xml")
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
