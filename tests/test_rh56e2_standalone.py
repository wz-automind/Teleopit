from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import mujoco
import numpy as np
import pytest

from teleopit.inputs.pico4_provider import PicoHandSnapshot, PicoHandState
from teleopit.sim.rh56e2_standalone import (
    Rh56e2StandaloneRuntime,
    snapshot_to_bihand_frame,
)

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts/run/run_rh56e2_sim.py"


def test_rh56e2_coordinate_axes_are_hidden_without_hiding_tip_markers() -> None:
    from teleopit.sim import viewer_subprocess

    hide_axes = getattr(viewer_subprocess, "hide_rh56e2_coordinate_axes", None)
    assert callable(hide_axes), "RH56E2 coordinate-axis hiding is not implemented"

    model = mujoco.MjModel.from_xml_string(
        """
<mujoco>
  <worldbody>
    <body>
      <geom type="cylinder" size="0.004 0.075" rgba="1 0 0 1"/>
      <geom type="sphere" size="0.015" rgba="1 0 0 1"/>
      <geom type="cylinder" size="0.004 0.075" rgba="0 1 0 1"/>
      <geom type="sphere" size="0.015" rgba="0 1 0 1"/>
      <geom type="cylinder" size="0.004 0.075" rgba="0 0 1 1"/>
      <geom type="sphere" size="0.015" rgba="0 0 1 1"/>
      <geom name="finger_tip_marker" type="sphere" size="0.005" rgba="1 0 0 1"/>
    </body>
  </worldbody>
</mujoco>
"""
    )

    assert hide_axes(model) == 6
    np.testing.assert_array_equal(model.geom_rgba[:6, 3], np.zeros(6))
    assert model.geom("finger_tip_marker").rgba[3] == 1.0


def test_robot_viewer_model_loader_hides_rh56e2_axes(tmp_path) -> None:
    from teleopit.sim import viewer_subprocess

    load_model = getattr(viewer_subprocess, "load_robot_viewer_model", None)
    assert callable(load_model), "robot viewer does not use an axis-hiding loader"

    xml_path = tmp_path / "hands.xml"
    xml_path.write_text(
        """
<mujoco model="hands">
  <worldbody>
    <geom name="axis" type="cylinder" size="0.004 0.075" rgba="1 0 0 1"/>
    <geom name="hand" type="sphere" size="0.02" rgba="1 1 1 1"/>
  </worldbody>
</mujoco>
"""
    )

    model = load_model(str(xml_path), title="Sim2Sim")

    assert model.geom("axis").rgba[3] == 0.0
    assert model.geom("hand").rgba[3] == 1.0


def _load_launcher():
    spec = importlib.util.spec_from_file_location("run_rh56e2_sim", LAUNCHER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_cli_help_has_no_policy_or_g1_arguments() -> None:
    result = subprocess.run(
        [sys.executable, str(LAUNCHER), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--bridge-advertise-ip" in result.stdout
    assert "policy" not in result.stdout.lower()
    assert "g1" not in result.stdout.lower()


def test_default_config_resolves_outside_repository_root(tmp_path, monkeypatch) -> None:
    launcher = _load_launcher()
    monkeypatch.chdir(tmp_path)

    path = launcher.resolve_config_path(None)

    assert path == (
        ROOT
        / "assets/rh56e2/somehand/configs/retargeting/bihand/inspire_rh56e2_bihand.yaml"
    )
    assert path.is_file()


class _ProviderFactory:
    instances = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.closed = 0
        self.__class__.instances.append(self)

    def close(self) -> None:
        self.closed += 1


class _EngineFactory:
    paths = []

    @classmethod
    def from_config_path(cls, path: str):
        cls.paths.append(path)
        return SimpleNamespace(
            left_engine=SimpleNamespace(hand_model="left-model"),
            right_engine=SimpleNamespace(hand_model="right-model"),
        )


class _SinkFactory:
    calls = []

    def __init__(self, left_model, right_model, **kwargs) -> None:
        self.__class__.calls.append((left_model, right_model, kwargs))


def test_build_runtime_passes_bridge_network_options() -> None:
    launcher = _load_launcher()
    _ProviderFactory.instances.clear()
    _EngineFactory.paths.clear()
    _SinkFactory.calls.clear()
    parser = launcher.build_parser()
    defaults = parser.parse_args([])
    assert defaults.bridge_host == "0.0.0.0"
    assert defaults.bridge_port == 63901
    assert defaults.timeout == 60.0
    assert defaults.bridge_start_timeout == 10.0

    args = parser.parse_args(
        [
            "--bridge-host",
            "127.0.0.1",
            "--bridge-port",
            "65000",
            "--bridge-advertise-ip",
            "192.168.50.62",
            "--timeout",
            "12.5",
            "--bridge-start-timeout",
            "3.5",
        ]
    )

    runtime = launcher.build_runtime(
        args,
        provider_cls=_ProviderFactory,
        engine_cls=_EngineFactory,
        sink_cls=_SinkFactory,
    )

    provider = _ProviderFactory.instances[-1]
    assert provider.kwargs == {
        "timeout": 12.5,
        "pause_button": None,
        "arms_button": None,
        "bridge_host": "127.0.0.1",
        "bridge_port": 65000,
        "bridge_advertise_ip": "192.168.50.62",
        "bridge_video_enabled": False,
        "bridge_start_timeout": 3.5,
    }
    assert runtime.provider is provider
    assert runtime.first_frame_timeout_s == 12.5
    assert _SinkFactory.calls == [("left-model", "right-model", {})]


def test_build_runtime_hides_axes_before_creating_bihand_window() -> None:
    launcher = _load_launcher()
    args = launcher.build_parser().parse_args([])

    def hand_model():
        model = mujoco.MjModel.from_xml_string(
            """
<mujoco>
  <worldbody>
    <geom name="axis" type="cylinder" size="0.004 0.075" rgba="0 1 0 1"/>
  </worldbody>
</mujoco>
"""
        )
        return SimpleNamespace(model=model)

    class EngineFactory:
        @classmethod
        def from_config_path(cls, _path: str):
            return SimpleNamespace(
                left_engine=SimpleNamespace(hand_model=hand_model()),
                right_engine=SimpleNamespace(hand_model=hand_model()),
            )

    class SinkFactory:
        final_model = None

        def __init__(self, left_model, right_model) -> None:
            del left_model, right_model
            model = mujoco.MjModel.from_xml_string(
                """
<mujoco>
  <worldbody>
    <geom name="axis" type="cylinder" size="0.004 0.075" rgba="0 1 0 1"/>
  </worldbody>
</mujoco>
"""
            )
            self._visualizer = SimpleNamespace(model=model)
            self.__class__.final_model = model

    launcher.build_runtime(
        args,
        provider_cls=_ProviderFactory,
        engine_cls=EngineFactory,
        sink_cls=SinkFactory,
    )

    assert SinkFactory.final_model is not None
    assert SinkFactory.final_model.geom("axis").rgba[3] == 0.0


def test_build_runtime_closes_provider_if_sink_creation_fails() -> None:
    launcher = _load_launcher()
    _ProviderFactory.instances.clear()
    args = launcher.build_parser().parse_args([])

    class BrokenSink:
        def __init__(self, *_args, **_kwargs) -> None:
            raise RuntimeError("viewer failed")

    with pytest.raises(RuntimeError, match="viewer failed"):
        launcher.build_runtime(
            args,
            provider_cls=_ProviderFactory,
            engine_cls=_EngineFactory,
            sink_cls=BrokenSink,
        )

    assert _ProviderFactory.instances[-1].closed == 1


def test_existing_g1_rh56e2_entrypoint_and_config_remain_present() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run/run_sim.py"),
            "--config-name",
            "pico4_sim_rh56e2",
            "--cfg",
            "job",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "policy_path:" in result.stdout
    assert "sim_hands:" in result.stdout
    assert "enabled: true" in result.stdout
