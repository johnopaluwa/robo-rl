# Verification: how every milestone gets proved

**The rule for this repo: a milestone is not done until someone else can re-run a
command and see the same result.** Plans, feelings and "it worked earlier" are
not evidence. This file is the registry of *how* each milestone is proved, and
`tools/verify.sh` is the thing you actually run.

```bash
./tools/verify.sh          # everything verifiable without ROS 2
./tools/verify.sh --ros2   # + real ROS 2 check (fails loudly if rclpy is missing)
python3 web/server.py      # watch the pipeline decide things, live in a browser

# no ROS 2 on this machine? two free ways to get a real one:
#   Codespaces  -> .devcontainer/ provisions ROS 2 Jazzy and runs the suite
#   GitHub Actions -> .github/workflows/verify.yml proves it on every push
# see docs/ROS2_ANYWHERE.md for costs, limits, and what each one actually proves
```

## Evidence tiers

Every claim in this repo sits in exactly one tier. Higher tiers never inherit
credibility from lower ones.

| Tier | What it is | What it proves | What it cannot prove |
| --- | --- | --- | --- |
| **T1 — unit tests** | `unittest`, no ROS needed | parsing, validation, thresholds, wording | integration of any kind |
| **T2 — proof artifacts** | `tools/proof_pipeline.py` → `artifacts/proofs/*.json` | pipeline behaviour, determinism, accounting | that DDS carries anything |
| **T3 — live demo** | `web/server.py` + `tools/ws_probe.py` | the running system, live protocol, commands | that ROS 2 is involved (unless `--mode ros2`) |
| **T4 — real ROS 2** | `tools/ros2_smoke_test.py` | rclpy pub/sub, schema on the wire, commands change real node state | physical hardware |
| **T5 — physical** | raw video of the arm on your bench | that it works in the real world | scaling, reliability over weeks |

Cloud ROS 2 counts as **T4**, not as a lower tier: Codespaces and CI run a real
ROS 2 runtime with real DDS. It is a real machine, just not yours. What it still
cannot do is touch hardware.

**Hard rule:** T1–T3 results are labelled `(sim)` and may never tick a milestone
whose text names ROS 2 or hardware. `tools/verify.sh` enforces this by keeping
the ROS 2 row `NOT VERIFIED` until the smoke test actually passes on a machine
with ROS 2 installed.

## Why simulation is still worth doing

The web viewer and the ROS 2 nodes share **one** implementation of behaviour:
`ros2_ws/src/robo_rl_demo/robo_rl_demo/pipeline.py`. The nodes are thin wrappers
around `CameraSource` + `PickerLogic`; the viewer drives the same two classes
over an in-process transport. That is what makes a green sim run meaningful
evidence *about the logic*, while still being honest that DDS is untested.

```
                     ┌──────────────────────────────┐
   ROS 2 mode ──────▶│  fake_camera ──▶ picker       │  rclpy + DDS
                     │      (thin wrappers)          │
                     ├──────────────────────────────┤
                     │      pipeline.py             │  ← the only real logic
                     │  CameraSource / PickerLogic   │
                     ├──────────────────────────────┤
   sim mode  ───────▶│  web viewer (server+runner)   │  in-process transport
                     └──────────────────────────────┘
```

The `shared pipeline imports no ROS` check in `tools/proof_pipeline.py` guards
this: if `pipeline.py` ever imports `rclpy`, the sim stops being evidence and
the proof fails.

## The registry

Status column reflects a real `./tools/verify.sh` run in an environment without
ROS 2. `MILESTONES.md` is the checkbox tracker; this is the proof tracker.

### Phase 0 — Niche lock

| Milestone | Proof | Command | Status |
| --- | --- | --- | --- |
| Chosen task written in README | README contains the mission sentence | `./tools/verify.sh` (Phase 0 row) | **PENDING** |
| 5 customer conversations | one file per conversation in `research-notes/interviews/`, counted by the script | `./tools/verify.sh` (Phase 0 row) | **PENDING (0/5)** |
| Dev environment set up | repo builds, tests run | `./tools/verify.sh` | **PASS** |
| `research-notes/log.md` started | file exists and is non-empty | `test -s research-notes/log.md` | **PASS** |

Phase 0 is deliberately not automatable beyond counting files. The proof of a
conversation is the notes you wrote down; the script only checks that they exist.

### Phase 1 — Python, math, ROS 2

| Milestone | Proof | Command | Status |
| --- | --- | --- | --- |
| Python without heavy LLM scaffolding | `pipeline.py` has no ROS import, is type-annotated, and 21 tests pass | `./tools/verify.sh` | **PASS** |
| Linear algebra + probability primer | not mechanically provable — evidence is notes in `research-notes/` | n/a | **NOT VERIFIED** |
| ROS 2 beginner tutorials completed | not mechanically provable — evidence is `research-notes/log.md` entries | n/a | **NOT VERIFIED** |
| Toy ROS 2 publisher/subscriber pair | `tools/ros2_smoke_test.py`: real nodes, real DDS, observer node, command round-trip | `./tools/verify.sh --ros2` | **VERIFIED in CI** ([run 37474982123](https://github.com/johnopaluwa/robo-rl/actions/runs/37474982123), ROS 2 Jazzy) |
| …the same, in a free cloud box | Codespaces devcontainer runs the suite on creation | `.devcontainer/` session | **READY** (see [ROS2_ANYWHERE.md](ROS2_ANYWHERE.md)) |
| …the same, automatically and publicly | CI job `ros2`: setup-ros jazzy, build, `verify.sh --ros2`, browser probe | push → Actions tab | **READY** (first run pending) |
| Browser sees live DDS, not a sim | `tools/ros2_viewer_check.sh` runs the real nodes + viewer and probes `/ws` with `--expect-ros2` | `./tools/ros2_viewer_check.sh` | **VERIFIED in CI** ([run 37490542247](https://github.com/johnopaluwa/robo-rl/actions/runs/37490542247), real detections reached the browser) |
| PyTorch blitz | not mechanically provable — artifact would be a training script in `simulation/train/` | n/a | **NOT VERIFIED** |

The ROS 2 row is the one that matters most right now. It stays unchecked until
you run the smoke test where ROS 2 exists. That is a feature: you will know the
exact moment your ROS 2 claim becomes true.

### Phase 2 — Simulation MVP

| Milestone | Proof | Command | Status |
| --- | --- | --- | --- |
| Simulator installed and running a demo env | screenshot/recording committed under `simulation/`, plus a script that reproduces it | `simulation/train/*.sh` (to be written) | NOT VERIFIED |
| Baseline PPO on a stock env | training log + config + eval output committed | `simulation/train/...` | NOT VERIFIED |
| Custom env for your task | env unit tests (spawn, reset, reward) like `test_pipeline.py` does for this repo | `python3 -m unittest` | NOT VERIFIED |
| Domain randomization implemented | test that asserts randomized parameters differ across resets | `python3 -m unittest` | NOT VERIFIED |
| LeRobot exploration | notes + a fine-tuning script that runs headless in CI | `research-notes/` | NOT VERIFIED |
| >80% success across randomized conditions | `simulation/videos/` video **and** a seeded eval script that prints the success rate | `simulation/eval.py --seed N` | NOT VERIFIED |

**Pattern to follow when Phase 2 starts:** every training run should write
`artifacts/proofs/<name>.json` with `seed`, `config_hash`, `episodes`,
`success_rate`, and the git commit. A video alone is not evidence — anyone can
cherry-pick a clip. A seeded eval that reproduces the number is.

### Phase 3 — Physical hardware

| Milestone | Proof | Status |
| --- | --- | --- |
| Arm + camera purchased | photo of the rig + serial numbers recorded in `research-notes/log.md` | NOT VERIFIED |
| Arm moves via ROS 2 / SDK | a `tools/arm_smoke_test.py` (mirroring `ros2_smoke_test.py`) that commands one safe motion and asserts the reported joint state changed | NOT VERIFIED |
| Perception pipeline | a test that feeds recorded frames through detection and asserts known objects are found, with the frames committed | NOT VERIFIED |
| Sim policy on real arm | **raw, unedited, continuous video** (no cuts) + intervention count logged from the dashboard | NOT VERIFIED |
| Teleoperation fallback | the dashboard's CALL SUPPORT path exercised on real hardware, with the intervention recorded | NOT VERIFIED |
| Multi-minute repetition video | one take, including failures and recoveries | NOT VERIFIED |

Physical milestone proofs are *not* automatable — they are recorded evidence with
a defined format. Define the format before you need it: continuous take, visible
clock, intervention log exported from the dashboard, and the git commit of the
policy shown on screen.

### Phase 4 — Dashboard & first pilot

| Milestone | Proof | Command | Status |
| --- | --- | --- | --- |
| Angular dashboard (camera, status, 3 buttons) | Angular unit tests + a Playwright run against a recorded fixture; the target protocol already exists here | `npm test` / `npx playwright test` (to be written) | NOT VERIFIED |
| rosbridge connecting ROS 2 to frontend | a probe like `tools/ws_probe.py` pointed at `rosbridge_suite` | `python3 tools/ws_probe.py --port 9090 --path /` | NOT VERIFIED |
| First free 2-week pilot | signed one-page pilot agreement + dated photo of install | n/a (upload to `research-notes/pilots/`) | NOT VERIFIED |
| Intervention-rate data collected | exported CSV from the dashboard, with a falling or flat trend chart | n/a | NOT VERIFIED |
| Paid RaaS contract | signed contract (redacted copy) | n/a | NOT VERIFIED |
| Bootstrap vs pre-seed decision | written memo in `docs/` with the numbers that drove it | n/a | NOT VERIFIED |

The prototype in `web/` is the **specification** for the Angular app: same state
snapshot shape, same command schema, same three buttons. When you build the real
dashboard, port `web/static/app.js` into components and keep the JSON contract —
the proof (the WebSocket probe) then works against either implementation.

## Current honest status

From the last `./tools/verify.sh` run in this sandbox (no ROS 2 available):

| proof | transport | status |
| --- | --- | --- |
| Cloud ROS 2 in CI (`ros2` job, milestone proof) | (ros2) | **PASS** (run 37474982123) |
| Cloud ROS 2 browser path (`ros2_viewer_check.sh`) | (ros2) | **PASS** ([run 37490542247](https://github.com/johnopaluwa/robo-rl/actions/runs/37490542247)) |
| Codespaces devcontainer suite | (ros2) | **READY — runs on create** |
| unit tests (21) | python 3 | **PASS** |
| pipeline logic proof (16 checks) | (sim) | **PASS** |
| live viewer + WebSocket command round-trip | (sim) | **PASS** |
| Phase 0: niche chosen in README | docs | **PENDING** |
| Phase 0: 5 customer conversations | docs | **PENDING (0/5)** |
| ROS 2 pub/sub + commands | (ros2) | **NOT VERIFIED** |

Simulation cannot tick the ROS 2 milestone. Nothing here can tick a hardware
milestone. That is the point of the table.

## Lessons this system has already paid for

Every one of these was a real bug found by running the checks, not by review.
They are written down because each is easy to reintroduce:

1. **`set -u` vs ROS 2 setup scripts.** `source /opt/ros/*/setup.bash` and
   colcon's overlay are not nounset-safe; the first unset variable they touch
   aborts your script with status 1 and a stderr line only. Relax nounset around
   those `source` lines, and assert the overlay file exists first.
2. **rclpy does not keep your subscriptions alive.** `create_subscription()`
   returns an object; if you discard it, Python's GC tears down the DDS
   subscription while the node stays in the graph. Symptom: `ros2 node list`
   shows your node, `ros2 topic hz` shows a healthy rate, and your node receives
   nothing. Hold a reference. (`tools/test_transport_lifetime.py` guards this.)
3. **Never `wait` on a `ros2 run` wrapper.** They can ignore SIGTERM, and an
   unbounded `wait` in a cleanup trap hangs until the CI step times out --
   turning a passing check into a red one. TERM, poll `kill -0`, then KILL.
4. **Wait for DDS discovery before judging a bridge.** A fresh rclpy node needs
   a moment to discover a publisher; probing at HTTP-ready (0.18s after start)
   races that and reports a false failure.
5. **Use-before-assign aborts silently under `set -u`** (e.g. a `note "...${VAR}"`
   line above the line that assigns `VAR`). Shellcheck does *not* catch this;
   `tools/test_shell_scripts.py` does.
6. **Standard a diagnostics channel before you need it.** A red check whose logs
   you cannot reach is worth nothing: this repo posts the failure detail as a PR
   comment, and CI job logs/artifacts were unreachable from the dev sandbox.

## Adding a proof for a new milestone

1. Write the smallest script that fails before the work and passes after it.
2. Make it print `PASS`/`FAIL` per check and write `artifacts/proofs/<name>.json`
   with `verdict`, `transport`, `proves[]`, `does_not_prove[]`.
3. Add it as a step in `tools/verify.sh` with a `record` line, so the summary
   table stays the single source of truth.
4. Add a row to this file. Say what it does *not* prove.
5. Tick the box in `MILESTONES.md` only when the script passes on the machine
   that has the real thing (ROS 2 box, arm, customer site).

## Gaps in this system (known, deliberate)

- **`artifacts/` is gitignored.** Proofs are reproducible, not committed, so
  nothing rots. If you want a proof in the repo, commit the script that
  regenerates it, not the output.
- **The CI workflow and devcontainer have not been executed yet.** They were
  written in a container without Docker or ROS 2, so their first run in Actions /
  Codespaces is the real test. That is stated here rather than hidden: an
  unverified claim should be visible, and a red run is information.
- **`colcon test` is deliberately not in CI.** The package's tests are run
  directly by `verify.sh` under the ROS 2 environment; wiring `colcon test` adds
  a pytest dependency that could not be verified from here. Add it once you can
  watch it run.
- **The sim's grasp model is a teaching model**, not a policy: `simulate_grasp`
  is a probability curve, not physics. It exists so the confidence/threshold
  trade-off is visible, and it is labelled as such in the code and the UI.
