# Pico-Driven Standalone RH56E2 Simulation Design

## Goal

Add a minimal Teleopit entry point that visualizes two RH56E2 hands in one
MuJoCo window and drives them from live Pico hand tracking. The standalone
path must not load the G1 model, a locomotion policy, or real hand hardware.

The existing G1 + RH56E2 simulation remains available and unchanged.

## User Interface

The default command is:

```bash
python scripts/run/run_rh56e2_sim.py
```

For hosts that need an explicit Pico Bridge advertisement address:

```bash
python scripts/run/run_rh56e2_sim.py \
  --bridge-advertise-ip 192.168.50.62
```

The existing combined simulation continues to use:

```bash
python scripts/run/run_sim.py \
  --config-name pico4_sim_rh56e2 \
  controller.policy_path=ckpt/track_g1.onnx
```

## Architecture

The new launcher is independent of `TeleopPipeline` and its G1 policy
validation. It composes the existing components directly:

1. `Pico4InputProvider` starts Pico Bridge and receives live hand snapshots.
2. `pico_hand_to_landmarks` converts each tracked Pico hand from 26 joints to
   the 21 landmarks expected by somehand.
3. `BiHandRetargetingEngine` loads the existing RH56E2 bihand configuration and
   computes left and right RH56E2 joint positions.
4. `BiHandOutputWindowSink` displays both RH56E2 models in a single MuJoCo
   window.

No G1 model, ONNX policy, BVH input, real-robot transport, or RH56E2 SDK write
path participates in this runtime.

## Runtime Behavior

The launcher waits for Pico input, processes each new hand snapshot once, and
updates the visualization. When one hand is temporarily untracked, its last
valid pose remains displayed while the other hand continues updating. When
tracking resumes, normal updates continue.

Only the two simulated E2 hands are shown by default. A separate Pico landmark
window is deliberately omitted to keep the normal workflow simple.

Closing the MuJoCo window or pressing `Ctrl+C` shuts down the visualization and
closes `Pico4InputProvider`, including its bridge receiver thread.

## Configuration and Paths

The launcher resolves the existing bihand retargeting configuration relative
to the repository root:

```text
assets/rh56e2/somehand/configs/retargeting/bihand/inspire_rh56e2_bihand.yaml
```

Command-line options expose only useful connection and startup controls, such
as the bridge host, port, advertisement IP, input timeout, and optional bihand
configuration override. Defaults match Teleopit's existing Pico configuration.

## Errors and Safety

Startup failures report the missing dependency or configuration path directly.
A Pico timeout reports that no tracking data was received instead of referring
to G1 or a missing policy. The runtime is simulation-only and must never open a
connection to physical RH56E2 hands or issue device commands.

## Verification

Automated tests use fakes for Pico input, retargeting, and the visualization to
verify:

- standalone startup does not require `controller.policy_path`;
- left and right tracked hands are converted and forwarded correctly;
- a missing hand preserves its previous displayed pose;
- duplicate Pico sequence numbers are not processed twice;
- provider and window resources close on normal exit and interruption;
- the existing G1 + RH56E2 configuration and entry point remain present.

A manual smoke test runs the default command with Pico Bridge and confirms that
both E2 models appear in one window and follow the corresponding hands.
