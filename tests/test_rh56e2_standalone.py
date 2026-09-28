from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from teleopit.inputs.pico4_provider import PicoHandSnapshot, PicoHandState
from teleopit.sim.rh56e2_standalone import (
    Rh56e2StandaloneRuntime,
    snapshot_to_bihand_frame,
)


def _hand(*, active: bool = True, present: bool = True, offset: float = 0.0) -> PicoHandState:
    joints = np.zeros((26, 7), dtype=np.float64)
    for index in range(26):
        joints[index, :3] = (index + offset, index + 100 + offset, index + 200 + offset)
    return PicoHandState(active=active, present=present, joints=joints)


def _snapshot(
    seq: int,
    *,
    left: PicoHandState | None = None,
    right: PicoHandState | None = None,
) -> PicoHandSnapshot:
    return PicoHandSnapshot(
        left=left if left is not None else _hand(active=False),
        right=right if right is not None else _hand(active=False),
        timestamp_s=float(seq),
        seq=seq,
    )


class _Provider:
    def __init__(self, snapshots=(), *, stay_available: bool = False) -> None:
        self.snapshots = list(snapshots)
        self.stay_available = stay_available
        self.closed = 0

    def is_available(self) -> bool:
        return self.stay_available or bool(self.snapshots)

    def get_hand_snapshot(self):
        if not self.snapshots:
            return None
        return self.snapshots.pop(0)

    def close(self) -> None:
        self.closed += 1


class _RetainingEngine:
    def __init__(self) -> None:
        self.frames = []
        self.left = "neutral-left"
        self.right = "neutral-right"

    def process(self, frame):
        self.frames.append(frame)
        if frame.left is not None:
            self.left = tuple(frame.left.landmarks_3d[0])
        if frame.right is not None:
            self.right = tuple(frame.right.landmarks_3d[0])
        return SimpleNamespace(left=self.left, right=self.right)


class _Sink:
    def __init__(self, *, running: bool = True) -> None:
        self.running = running
        self.results = []
        self.closed = 0

    @property
    def is_running(self) -> bool:
        return self.running

    def on_result(self, result) -> None:
        self.results.append(result)

    def close(self) -> None:
        self.closed += 1
        self.running = False


def test_snapshot_to_bihand_frame_converts_active_left_and_right() -> None:
    frame = snapshot_to_bihand_frame(
        _snapshot(1, left=_hand(), right=_hand(offset=1000.0))
    )

    assert frame.left is not None
    assert frame.right is not None
    assert frame.left.hand_side == "left"
    assert frame.right.hand_side == "right"
    np.testing.assert_array_equal(frame.left.landmarks_3d[0], (1.0, -201.0, 101.0))
    np.testing.assert_array_equal(frame.left.landmarks_3d[-1], (25.0, -225.0, 125.0))
    np.testing.assert_array_equal(frame.right.landmarks_3d[0], (1001.0, -1201.0, 1101.0))


def test_snapshot_to_bihand_frame_omits_inactive_or_missing_hand() -> None:
    frame = snapshot_to_bihand_frame(
        _snapshot(
            1,
            left=_hand(active=False),
            right=_hand(active=True, present=False),
        )
    )

    assert frame.left is None
    assert frame.right is None
    assert not frame.has_detection


def test_runtime_processes_each_sequence_once() -> None:
    provider = _Provider(
        [
            _snapshot(1, left=_hand()),
            _snapshot(1, left=_hand(offset=10.0)),
            _snapshot(2, right=_hand()),
        ]
    )
    engine = _RetainingEngine()
    sink = _Sink()

    processed = Rh56e2StandaloneRuntime(
        provider,
        engine,
        sink,
        sleep_fn=lambda _: None,
    ).run()

    assert processed == 2
    assert len(engine.frames) == 2
    assert len(sink.results) == 2
    assert provider.closed == 1
    assert sink.closed == 1


def test_runtime_preserves_missing_hand_through_engine_result() -> None:
    provider = _Provider(
        [
            _snapshot(1, left=_hand(), right=_hand(offset=1000.0)),
            _snapshot(2, left=_hand(offset=10.0), right=_hand(active=False)),
        ]
    )
    engine = _RetainingEngine()
    sink = _Sink()

    Rh56e2StandaloneRuntime(
        provider,
        engine,
        sink,
        sleep_fn=lambda _: None,
    ).run()

    assert engine.frames[1].left is not None
    assert engine.frames[1].right is None
    assert sink.results[1].right == sink.results[0].right
    assert sink.results[1].left != sink.results[0].left


def test_runtime_times_out_when_no_hand_packet_arrives() -> None:
    provider = _Provider(stay_available=True)
    sink = _Sink()
    clock = iter((0.0, 0.25, 1.01))

    with pytest.raises(TimeoutError, match="No Pico hand tracking data"):
        Rh56e2StandaloneRuntime(
            provider,
            _RetainingEngine(),
            sink,
            first_frame_timeout_s=1.0,
            sleep_fn=lambda _: None,
            monotonic_fn=lambda: next(clock),
        ).run()

    assert provider.closed == 1
    assert sink.closed == 1


def test_runtime_exits_when_viewer_closes_before_tracking() -> None:
    provider = _Provider(stay_available=True)
    sink = _Sink(running=False)

    processed = Rh56e2StandaloneRuntime(
        provider,
        _RetainingEngine(),
        sink,
        sleep_fn=lambda _: None,
    ).run()

    assert processed == 0
    assert provider.closed == 1
    assert sink.closed == 1


def test_runtime_closes_provider_and_sink_on_keyboard_interrupt() -> None:
    provider = _Provider(stay_available=True)
    sink = _Sink()

    processed = Rh56e2StandaloneRuntime(
        provider,
        _RetainingEngine(),
        sink,
        sleep_fn=lambda _: (_ for _ in ()).throw(KeyboardInterrupt),
    ).run()

    assert processed == 0
    assert provider.closed == 1
    assert sink.closed == 1
