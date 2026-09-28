"""Standalone Pico hand tracking to RH56E2 MuJoCo visualization."""

from __future__ import annotations

import time
from typing import Any, Callable

from teleopit.inputs.pico4_provider import PicoHandSnapshot
from teleopit.sim2real.hands.pico_landmarks import pico_hand_to_landmarks


def snapshot_to_bihand_frame(snapshot: PicoHandSnapshot) -> Any:
    """Convert one Pico hand snapshot to somehand's two-hand frame."""
    from somehand.api import BiHandFrame, HandFrame

    left = None
    if snapshot.left.present and snapshot.left.active:
        left = HandFrame(
            pico_hand_to_landmarks(snapshot.left.joints),
            None,
            "left",
        )

    right = None
    if snapshot.right.present and snapshot.right.active:
        right = HandFrame(
            pico_hand_to_landmarks(snapshot.right.joints),
            None,
            "right",
        )

    return BiHandFrame(left=left, right=right)


class Rh56e2StandaloneRuntime:
    """Poll Pico snapshots and forward retargeted poses to one bihand viewer."""

    def __init__(
        self,
        provider: Any,
        engine: Any,
        sink: Any,
        *,
        first_frame_timeout_s: float = 60.0,
        poll_interval_s: float = 0.01,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.provider = provider
        self.engine = engine
        self.sink = sink
        self.first_frame_timeout_s = float(first_frame_timeout_s)
        self.poll_interval_s = float(poll_interval_s)
        self._sleep = sleep_fn
        self._monotonic = monotonic_fn

    def run(self) -> int:
        processed = 0
        last_seq: int | None = None
        first_packet_at = self._monotonic()

        try:
            while self.provider.is_available() and self.sink.is_running:
                snapshot = self.provider.get_hand_snapshot()
                if snapshot is None:
                    if self._monotonic() - first_packet_at >= self.first_frame_timeout_s:
                        raise TimeoutError(
                            "No Pico hand tracking data received within "
                            f"{self.first_frame_timeout_s:.1f}s"
                        )
                    self._sleep(self.poll_interval_s)
                    continue

                seq = int(snapshot.seq)
                if seq == last_seq:
                    self._sleep(self.poll_interval_s)
                    continue
                last_seq = seq

                frame = snapshot_to_bihand_frame(snapshot)
                if frame.has_detection:
                    result = self.engine.process(frame)
                    self.sink.on_result(result)
                    processed += 1

                self._sleep(self.poll_interval_s)
        except KeyboardInterrupt:
            pass
        finally:
            try:
                self.sink.close()
            finally:
                self.provider.close()

        return processed


__all__ = ["Rh56e2StandaloneRuntime", "snapshot_to_bihand_frame"]
