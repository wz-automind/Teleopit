from __future__ import annotations

import hydra
from omegaconf import DictConfig

from teleopit.pipeline_rh56e2 import TeleopPipelineRh56e2
from teleopit.runtime.common import cfg_get
from teleopit.runtime.console import PlainConsole, configure_runtime_logging, sim_keyboard_controls
from teleopit.runtime.cli import validate_policy_path


def _sim_status(cfg: DictConfig) -> tuple[tuple[str, str], ...]:
    input_cfg = cfg_get(cfg, "input", {}) or {}
    provider = str(cfg_get(input_cfg, "provider", "bvh")).lower()
    viewers = str(cfg_get(cfg, "viewers", "none"))
    if provider == "pico4":
        keyboard_cfg = cfg_get(cfg, "keyboard", {}) or {}
        state = "STANDING" if bool(cfg_get(keyboard_cfg, "enabled", False)) else "MOCAP"
        return (("State", state), ("Input", "Pico4 live"), ("Viewers", viewers), ("Hands", "RH56E2"))
    return (("State", "MOCAP"), ("Input", "BVH"), ("Viewers", viewers), ("Hands", "RH56E2"))


@hydra.main(version_base=None, config_path="../../teleopit/configs", config_name="pico4_sim_rh56e2")
def main(cfg: DictConfig) -> None:
    configure_runtime_logging(cfg, force=True)
    validate_policy_path(cfg, "run_sim_rh56e2.py")
    console = PlainConsole(title="Teleopit RH56E2 sim2sim")
    pipeline = TeleopPipelineRh56e2(cfg, console=console)
    num_steps = int(cfg.get("num_steps", 0))
    events = []
    if cfg_get(cfg, "input.provider", None) == "pico4":
        events.append("waiting for Pico4 body and hand tracking data")
    console.start(status=_sim_status(cfg), controls=sim_keyboard_controls(cfg), events=events)
    result = pipeline.run(num_steps=num_steps)
    console.event(str(result))


if __name__ == "__main__":
    main()
