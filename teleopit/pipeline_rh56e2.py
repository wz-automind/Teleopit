"""Parallel RH56E2 full-body simulation pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from omegaconf import DictConfig

from teleopit.bus.in_process import InProcessBus
from teleopit.controllers.observation import VelCmdObservationBuilder
from teleopit.controllers.rl_policy import RLPolicyController
from teleopit.inputs import BVHInputProvider, Pico4InputProvider
from teleopit.inputs.pico_video import PicoVideoRuntime, parse_pico_video_config
from teleopit.retargeting.core import RetargetingModule
from teleopit.robots.mujoco_robot_rh56e2 import MuJoCoRobotRh56e2
from teleopit.runtime.common import cfg_get
from teleopit.runtime.console import PlainConsole
from teleopit.runtime.factory import build_inference_components
from teleopit.sim.loop_rh56e2 import SimulationLoopRh56e2


class TeleopPipelineRh56e2:
    def __init__(self, cfg: DictConfig | dict[str, Any], *, console: PlainConsole | None = None) -> None:
        self.cfg = cfg
        project_root = Path(__file__).resolve().parent.parent
        components = build_inference_components(
            cfg,
            project_root,
            robot_cls=MuJoCoRobotRh56e2,
            controller_cls=RLPolicyController,
            obs_builder_cls=VelCmdObservationBuilder,
            bvh_input_cls=BVHInputProvider,
            pico4_input_cls=Pico4InputProvider,
            retargeter_cls=RetargetingModule,
        )
        self.robot = components.robot
        self.controller = components.controller
        self.obs_builder = components.obs_builder
        self.input_provider = components.input_provider
        self.retargeter = components.retargeter
        self.bus = InProcessBus()
        input_cfg = cfg_get(cfg, "input", {})
        self.video_runtime = PicoVideoRuntime(
            provider=self.input_provider,
            config=parse_pico_video_config(input_cfg),
            robot=self.robot,
        )
        # build_inference_components intentionally returns a reduced
        # simulation config. Preserve RH56E2-specific top-level settings when
        # constructing the parallel simulation loop.
        sim_cfg = dict(components.sim_cfg)
        sim_cfg["sim_hands"] = cfg_get(cfg, "sim_hands", {}) or {}
        self.loop = SimulationLoopRh56e2(
            cast(Any, self.robot),
            cast(Any, self.controller),
            cast(Any, self.obs_builder),
            cast(Any, self.bus),
            sim_cfg,
            viewers=components.viewers,
            video_runtime=self.video_runtime,
            console=console,
        )

    def run(self, num_steps: int) -> dict[str, float | int | str]:
        if num_steps < 0:
            raise ValueError("num_steps must be non-negative (0 = infinite)")
        self.controller.reset()
        return dict(self.loop.run(cast(Any, self.input_provider), cast(Any, self.retargeter), num_steps=num_steps))
