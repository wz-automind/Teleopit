# RH56E2 Pico Standalone Simulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-command, Pico-driven, two-hand RH56E2 MuJoCo viewer that does not load G1 or an ONNX policy, while preserving the existing G1 + RH56E2 simulation.

**Architecture:** A focused runtime module converts `PicoHandSnapshot` values into somehand bihand frames and owns a small polling/cleanup loop. A thin argparse launcher constructs `Pico4InputProvider`, `BiHandRetargetingEngine`, and `BiHandOutputWindowSink` with lazy optional-dependency imports.

**Tech Stack:** Python 3.10, Pico Bridge, somehand, MuJoCo, argparse, pytest

**Spec:** `docs/superpowers/specs/2026-09-28-rh56e2-pico-standalone-sim-design.md`

## Global Constraints

- The default command is `python scripts/run/run_rh56e2_sim.py`.
- Show left and right RH56E2 models in one MuJoCo window.
- Do not load G1, `TeleopPipeline`, an ONNX policy, BVH input, or real-hand transports.
- Keep `scripts/run/run_sim.py --config-name pico4_sim_rh56e2 controller.policy_path=ckpt/track_g1.onnx` working and documented.
- Resolve the default bihand config from `assets/rh56e2/somehand/configs/retargeting/bihand/inspire_rh56e2_bihand.yaml` relative to the repository, not the current directory.
- Always close the Pico provider and MuJoCo sink on normal exit, window close, timeout, or `KeyboardInterrupt`.

## Review Focus

- No hand packet ever arrives: fail after the configured timeout with a Pico-hand-specific message; Task 1 tests this.
- Only one hand is tracked: update it while preserving the other engine result; Task 1 tests this.
- A packet sequence is repeated: do not retarget or redraw it twice; Task 1 tests this.
- The viewer is closed before tracking starts: return normally and close both resources; Task 1 tests this.
- The command runs outside the repository root: resolve the model config correctly; Task 2 tests this.

---

### Task 1: Standalone Pico-to-RH56E2 Runtime

**Files:**
- Create: `teleopit/sim/rh56e2_standalone.py`
- Create: `tests/test_rh56e2_standalone.py`

**Interfaces:**
- Consumes: `PicoHandSnapshot`, `pico_hand_to_landmarks`, somehand `HandFrame` and `BiHandFrame`, and provider/engine/sink objects exposing their existing public methods.
- Produces: `snapshot_to_bihand_frame(snapshot) -> BiHandFrame` and `Rh56e2StandaloneRuntime(provider, engine, sink, *, first_frame_timeout_s=60.0, poll_interval_s=0.01, sleep_fn=time.sleep, monotonic_fn=time.monotonic).run() -> int`.

- [ ] **Step 1: Write failing conversion and runtime tests**

Add tests named:

- `test_snapshot_to_bihand_frame_converts_active_left_and_right`
- `test_snapshot_to_bihand_frame_omits_inactive_or_missing_hand`
- `test_runtime_processes_each_sequence_once`
- `test_runtime_preserves_missing_hand_through_engine_result`
- `test_runtime_times_out_when_no_hand_packet_arrives`
- `test_runtime_exits_when_viewer_closes_before_tracking`
- `test_runtime_closes_provider_and_sink_on_keyboard_interrupt`

Use fake provider, engine, and sink objects. Assert that the one-hand frame contains `None` for the missing side, that duplicate sequence IDs cause one `engine.process` call, that the timeout says `No Pico hand tracking data`, and that cleanup calls each resource exactly once.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m pytest -q tests/test_rh56e2_standalone.py`

Expected: FAIL because `teleopit.sim.rh56e2_standalone` does not exist.

- [ ] **Step 3: Implement the conversion function and runtime loop**

Implement `snapshot_to_bihand_frame(snapshot: PicoHandSnapshot) -> BiHandFrame` with lazy somehand imports. Convert only hands whose `present` and `active` fields are both true.

Implement `Rh56e2StandaloneRuntime.run() -> int` so it polls snapshots, rejects duplicate `seq` values, calls `engine.process` only for a frame with at least one detection, forwards the result to `sink.on_result`, returns the processed-frame count, and closes resources in `finally`.

- [ ] **Step 4: Run the focused test and verify success**

Run: `python -m pytest -q tests/test_rh56e2_standalone.py`

Expected: all Task 1 tests PASS.

- [ ] **Step 5: Commit the runtime**

```bash
git add teleopit/sim/rh56e2_standalone.py tests/test_rh56e2_standalone.py
git commit -m "feat: add standalone RH56E2 simulation runtime"
```

### Task 2: Minimal Command-Line Launcher

**Files:**
- Create: `scripts/run/run_rh56e2_sim.py`
- Modify: `tests/test_rh56e2_standalone.py`

**Interfaces:**
- Consumes: `Rh56e2StandaloneRuntime` and `snapshot_to_bihand_frame` from Task 1; `Pico4InputProvider`; `BiHandRetargetingEngine.from_config_path`; `BiHandOutputWindowSink`.
- Produces: `build_parser() -> argparse.ArgumentParser`, `resolve_config_path(raw: str | Path | None) -> Path`, `build_runtime(args: argparse.Namespace) -> Rh56e2StandaloneRuntime`, and `main(argv: Sequence[str] | None = None) -> int`.

- [ ] **Step 1: Write failing CLI and construction tests**

Add tests named:

- `test_cli_help_has_no_policy_or_g1_arguments`
- `test_default_config_resolves_outside_repository_root`
- `test_build_runtime_passes_bridge_network_options`
- `test_build_runtime_closes_provider_if_sink_creation_fails`
- `test_existing_g1_rh56e2_entrypoint_and_config_remain_present`

Inject or monkeypatch provider, engine, and sink factories. Assert defaults `0.0.0.0`, `63901`, `60.0`, and `10.0`; assert `--bridge-advertise-ip` is forwarded; and assert the existing `scripts/run/run_sim.py` and `teleopit/configs/pico4_sim_rh56e2.yaml` still exist.

- [ ] **Step 2: Run the focused CLI tests and verify failure**

Run: `python -m pytest -q tests/test_rh56e2_standalone.py -k 'cli or config or build_runtime or existing_g1'`

Expected: FAIL because the launcher and factory do not exist.

- [ ] **Step 3: Implement the launcher**

Add argparse options `--config`, `--bridge-host`, `--bridge-port`, `--bridge-advertise-ip`, `--timeout`, and `--bridge-start-timeout`. Construct the engine, then `Pico4InputProvider` with controller buttons and video disabled, and finally the bihand sink from the existing config. If sink construction fails, close the already-created provider. Print a short startup summary and return zero after the runtime exits.

Keep optional imports inside `build_runtime` so importing the parser does not require MuJoCo, Pico Bridge, or somehand.

- [ ] **Step 4: Run launcher help and focused tests**

Run: `python scripts/run/run_rh56e2_sim.py --help`

Expected: exit 0, list Pico bridge options, and contain no G1 or policy option.

Run: `python -m pytest -q tests/test_rh56e2_standalone.py`

Expected: all standalone tests PASS.

- [ ] **Step 5: Commit the launcher**

```bash
git add scripts/run/run_rh56e2_sim.py tests/test_rh56e2_standalone.py
git commit -m "feat: add standalone RH56E2 Pico command"
```

### Task 3: User Documentation and Regression Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/zh/usage.md`
- Modify: `tests/test_rh56e2_standalone.py`

**Interfaces:**
- Consumes: the Task 2 command-line interface.
- Produces: concise Chinese instructions distinguishing E2-only simulation from G1 + E2 simulation.

- [ ] **Step 1: Write failing documentation assertions**

Add `test_docs_distinguish_standalone_e2_from_g1_e2` and assert both documents contain `run_rh56e2_sim.py`, state that it needs no ONNX policy, and retain the `pico4_sim_rh56e2` combined command with `controller.policy_path=ckpt/track_g1.onnx`.

- [ ] **Step 2: Run the documentation test and verify failure**

Run: `python -m pytest -q tests/test_rh56e2_standalone.py::test_docs_distinguish_standalone_e2_from_g1_e2`

Expected: FAIL because the standalone command is not documented.

- [ ] **Step 3: Update the concise Chinese usage text**

Document the E2-only command first, its optional `--bridge-advertise-ip`, and that it opens one two-hand window without G1 or policy loading. Keep the existing combined simulation immediately afterward and add the required policy argument to any incomplete example.

- [ ] **Step 4: Run focused and regression tests**

Run: `python -m pytest -q tests/test_rh56e2_standalone.py tests/test_rh56e2_config.py tests/test_rh56e2_integration.py tests/test_rh56e2_resources.py tests/test_cli_entrypoints.py`

Expected: all selected tests PASS (private-SDK-dependent tests may report their existing clean skips).

Run: `python -m compileall -q teleopit scripts tests`

Expected: exit 0 with no syntax errors.

- [ ] **Step 5: Perform the environment smoke checks**

Run: `python scripts/run/run_rh56e2_sim.py --help`

Expected: exit 0 without loading G1 or requiring `controller.policy_path`.

When Pico is available, run: `python scripts/run/run_rh56e2_sim.py`

Expected: one MuJoCo window shows both RH56E2 hands; closing the window exits cleanly. Record this as a manual hardware/UI check rather than making it an automated-test requirement.

- [ ] **Step 6: Commit documentation and regression coverage**

```bash
git add README.md docs/zh/usage.md tests/test_rh56e2_standalone.py
git commit -m "docs: add standalone RH56E2 simulation workflow"
```
