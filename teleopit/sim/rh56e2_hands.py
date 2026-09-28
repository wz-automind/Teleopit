"""PICO hand tracking -> somehand -> embedded RH56E2 actuators."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from teleopit.runtime.common import cfg_get
from teleopit.sim2real.hands.pico_landmarks import pico_hand_to_landmarks

_logger = logging.getLogger(__name__)

LEFT_JOINTS = (
    "L_pinky_proximal_joint",
    "L_ring_proximal_joint",
    "L_middle_proximal_joint",
    "L_index_proximal_joint",
    "L_thumb_proximal_pitch_joint",
    "L_thumb_proximal_yaw_joint",
)
RIGHT_JOINTS = (
    "R_pinky_proximal_joint",
    "R_ring_proximal_joint",
    "R_middle_proximal_joint",
    "R_index_proximal_joint",
    "R_thumb_proximal_pitch_joint",
    "R_thumb_proximal_yaw_joint",
)


class Rh56e2SimHands:
    def __init__(self, robot: Any, input_provider: Any, cfg: Any) -> None:
        from somehand.api import BiHandFrame, BiHandRetargetingEngine, HandFrame

        self._BiHandFrame = BiHandFrame
        self._HandFrame = HandFrame
        self.robot = robot
        self.provider = input_provider
        sh = cfg_get(cfg, "sim_hands", {}) or {}
        raw = str(
            cfg_get(
                sh,
                "config",
                "assets/rh56e2/somehand/configs/retargeting/bihand/inspire_rh56e2_bihand.yaml",
            )
        )
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = (Path(__file__).resolve().parents[2] / p).resolve()
        if not p.exists():
            raise FileNotFoundError(f"RH56E2 bihand config not found: {p}")
        self.engine = BiHandRetargetingEngine.from_config_path(str(p))
        self._last_seq = None
        self._lq = self._joint_qpos_indices(
            self.engine.left_engine.hand_model.model, LEFT_JOINTS
        )
        self._rq = self._joint_qpos_indices(
            self.engine.right_engine.hand_model.model, RIGHT_JOINTS
        )
        self._la = self._actuator_indices(robot.model, LEFT_JOINTS)
        self._ra = self._actuator_indices(robot.model, RIGHT_JOINTS)
        _logger.info(
            "RH56E2 sim hands enabled: L=%s R=%s", self._la.tolist(), self._ra.tolist()
        )

    @staticmethod
    def _joint_qpos_indices(model, names):
        out = []
        for name in names:
            jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
            if jid < 0:
                raise ValueError(f"somehand model missing joint {name}")
            out.append(int(model.jnt_qposadr[jid]))
        return np.asarray(out, dtype=np.int32)

    @staticmethod
    def _actuator_indices(model, names):
        wanted, found = set(names), {}
        for aid in range(model.nu):
            jid = int(model.actuator_trnid[aid][0])
            if jid < 0:
                continue
            jn = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, jid)
            if jn in wanted:
                found[jn] = aid
        missing = [n for n in names if n not in found]
        if missing:
            raise ValueError(f"Combined model missing RH56E2 actuators: {missing}")
        return np.asarray([found[n] for n in names], dtype=np.int32)

    def tick(self) -> None:
        fn = getattr(self.provider, "get_hand_snapshot", None)
        if not callable(fn):
            return
        s = fn()
        if s is None or self._last_seq == int(s.seq):
            return
        self._last_seq = int(s.seq)
        lf = rf = None
        if bool(s.left.present) and bool(s.left.active):
            lf = self._HandFrame(pico_hand_to_landmarks(s.left.joints), None, "left")
        if bool(s.right.present) and bool(s.right.active):
            rf = self._HandFrame(pico_hand_to_landmarks(s.right.joints), None, "right")
        if lf is None and rf is None:
            return
        result = self.engine.process(self._BiHandFrame(left=lf, right=rf))
        l = np.asarray(result.left.qpos, dtype=np.float64)[self._lq]
        r = np.asarray(result.right.qpos, dtype=np.float64)[self._rq]
        self.robot.data.ctrl[self._la] = l
        self.robot.data.ctrl[self._ra] = r
