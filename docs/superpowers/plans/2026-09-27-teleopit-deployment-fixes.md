# Teleopit E2 Deployment Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the E2 launch/install instructions and scripts consistent with the merged Teleopit and independent SDK.

**Architecture:** Keep the existing G1 runtime and SDK interface. Normalize the PICO address in the common launcher; bootstrap offline build tools before editable installation and explicitly replace the supplied SDK wheel.

**Tech Stack:** Bash, Python 3.10+, pip, pytest, Hydra.

**Spec:** User-approved review findings in this conversation: fix obsolete branches, host PICO address forwarding, offline build dependency ordering, developer dependencies, same-version SDK replacement, and documentation links/history.

## Global Constraints

- Preserve remote master edits; merge and push to master as requested.
- No hardware connections or robot motion; config-only launch tests.
- Do not change control algorithms, write interlocks, SDK version, or model distribution policy.
- Keep private SDK and model data out of the public repository.

## Review Focus

- Both host/onboard launchers: empty address and explicit Hydra override precedence.
- Offline installer: bootstrap failure stops later installs without network fallback.
- Same-version SDK replacement must not force reinstall unrelated dependencies.
- Fresh developer environment must include Ruff as well as pytest.
- Docs must distinguish fresh checkout from prepared local environments and real hardware validation.

### Task 1: Repair launcher and offline installer contracts

**Files:** scripts/run/run_sim2real_rh56e2.sh, scripts/run/run_unitree_g1_rh56e2.sh, scripts/setup/install_rh56e2.sh, tests/test_rh56e2_launchers.py.

**Interfaces:** PICO_ADVERTISE_IP supplies input.bridge_advertise_ip; explicit CLI overrides win. Offline --wheelhouse must bootstrap setuptools>=61.0 and wheel, replace only the SDK using --force-reinstall --no-deps, then install runtime dependencies and checkout.

- [ ] Add parameterized config-only tests for both launchers (set, empty, CLI override).
- [ ] Add subprocess-boundary installer tests checking actual emitted pip arguments, bootstrap order, and early exit. No real installs into the user's environment.
- [ ] Run focused tests; expect missing address and bootstrap/reinstall assertions to fail.
- [ ] Implement minimal script changes and update the existing missing-dependency expectation for the bootstrap stage.
- [ ] Run tests/test_rh56e2_launchers.py; expect all pass; commit.

### Task 2: Align dependencies and stable user documentation

**Files:** pyproject.toml, docs/zh/usage.md, docs/zh/deployment.md, MIGRATION.md, README.md, AGENTS.md.

**Interfaces:** [dev] includes Ruff; SDK core import remains rh56e2_sdk. Usage clones master/main, documents SDK replacement and CLI address priority. Deployment installer owns build-tool bootstrap.

- [ ] Add Ruff to developer dependencies and document developer-only setup separately from normal use.
- [ ] Correct clone branches, environment creation order, SDK replacement instructions and tactile links; remove prepared-local-environment assumptions.
- [ ] Label migration verification statements as historical; preserve external resource limitations.
- [ ] Validate changed Bash scripts, Markdown links, diff whitespace, focused checks and full pytest suite; expect pass with existing upstream skip/warnings.
- [ ] Commit; request fresh read-only review, address blocking findings, merge master and verify/push normally (never force).
