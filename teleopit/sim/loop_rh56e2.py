"""Simulation loop variant that uses the RH56E2-aware session."""

from __future__ import annotations

from typing import Any, cast

from teleopit.interfaces import InputProvider, Retargeter
from teleopit.sim.loop import SimulationLoop


class SimulationLoopRh56e2(SimulationLoop):
    """Keep the stock loop intact while dispatching to the RH56E2 session."""

    def run(
        self,
        input_provider: InputProvider,
        retargeter: Retargeter,
        num_steps: int,
    ) -> dict[str, float | int]:
        from teleopit.sim.session_rh56e2 import SimLoopSessionRh56e2

        session = SimLoopSessionRh56e2(self, input_provider, retargeter, num_steps)
        return session.run()

    def run_headless(
        self,
        input_provider: InputProvider,
        retargeter: Retargeter,
        num_steps: int,
    ) -> dict[str, float | int]:
        return self.run(input_provider=input_provider, retargeter=retargeter, num_steps=num_steps)
