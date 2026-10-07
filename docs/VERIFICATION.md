# Verification: how every milestone gets proved

**The rule for this repo: a milestone is not done until someone else can re-run a
command and see the same result.** Plans, feelings and "it worked earlier" are
not evidence. This file is the registry of *how* each milestone is proved, and
`tools/verify.sh` is the thing you actually run.

```bash
./tools/verify.sh            # proofs that need neither ROS 2 nor hardware
./tools/verify.sh --ros2     # + real ROS 2 check (fails loudly if rclpy is missing)
python3 web/server.py        # watch the pipeline decide things, live in a browser

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
| **T2 — reproducible headless proofs** | `tools/proof_pipeline.py` → `artifacts/proofs/*.json` | pipeline logic, command schema, thresholds | ROS 2/DDS, physical gripper contact, or real-world behavior |
| **T3 — live demo** | `web/server.py` + `tools/ws_probe.py` | the running system, live protocol, commands | that ROS 2 is involved (unless `--mode ros2`) |
| **T4 — real ROS 2** | `tools/ros2_smoke_test.py` | rclpy pub/sub, schema on the wire, commands change real node state | physical hardware |
| **T5 — physical / real-robot evidence** | raw video, dataset/checkpoint/eval records from the bench | that it works in the real world | scaling, reliability over weeks |

Cloud ROS 2 counts as **T4**, not as a lower tier: Codespaces and CI run a real
ROS 2 runtime with real DDS. It is a real machine, just not yours. What it still
cannot do is touch hardware.

**Hard rule:** T1–T3 results are labelled `(sim)` and may never tick a milestone
whose text names ROS 2 or hardware. `tools/verify.sh` enforces this by keeping
the ROS 2 row `NOT VERIFIED` until the smoke test actually passes on a machine
with ROS 2 installed.

## Why the viewer's sim mode is still worth having

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

Status column reflects reproducible commands. The base interpreter here has no
ROS 2. `docs/ROADMAP.md` holds the plan and its checkboxes; this file is the
proof tracker — what each milestone's evidence actually is.

### Phase 0 — Niche lock & demo rig

| Milestone | Proof | Command | Status |
| --- | --- | --- | --- |
| Chosen task written in README | README contains the mission sentence | `./tools/verify.sh` (Phase 0 row) | **PASS** (bakery tray loading; still a hypothesis pending interviews) |
| 5 customer conversations | one file per conversation in `research-notes/interviews/`, counted by the script | `./tools/verify.sh` (Phase 0 row) | **PENDING (0/5)** |
| Demo rig ordered & teleoperating | dated order note + bench video of leader→follower teleop in `research-notes/log.md` | n/a (upload evidence to `log.md`) | NOT VERIFIED |
| Dev environment set up | repo builds, tests run | `./tools/verify.sh` | **PASS** |
| `research-notes/log.md` started | file exists and is non-empty | `test -s research-notes/log.md` | **PASS** |

Phase 0 is deliberately not automatable beyond counting files. The proof of a
conversation is the notes you wrote down; the script only checks that they exist.

### Foundations — Python & ROS 2 plumbing (proved; used again in Phase 3)

These were built under the old plan's "Phase 1" and remain live infrastructure:
the same nodes/wrappers are the pattern the Phase 3 policy runner will follow.

| Milestone | Proof | Command | Status |
| --- | --- | --- | --- |
| Python without heavy LLM scaffolding | `pipeline.py` has no ROS import, is type-annotated, and its tests pass | `./tools/verify.sh` | **PASS** |
| Toy ROS 2 publisher/subscriber pair | `tools/ros2_smoke_test.py`: real nodes, real DDS, observer node, command round-trip | `./tools/verify.sh --ros2` | **VERIFIED in CI** ([run 37474982123](https://github.com/johnopaluwa/robo-rl/actions/runs/37474982123), ROS 2 Jazzy) |
| …the same, in a free cloud box | Codespaces devcontainer runs the suite on creation | `.devcontainer/` session | **READY** (see [ROS2_ANYWHERE.md](ROS2_ANYWHERE.md)) |
| …the same, automatically and publicly | CI job `ros2`: setup-ros jazzy, build, `verify.sh --ros2`, browser probe | push → Actions tab | **VERIFIED in CI** (runs 37474982123 and 37490542247) |
| Browser sees live DDS, not a sim | `tools/ros2_viewer_check.sh` runs the real nodes + viewer and probes `/ws` with `--expect-ros2` | `./tools/ros2_viewer_check.sh` | **VERIFIED in CI** ([run 37490542247](https://github.com/johnopaluwa/robo-rl/actions/runs/37490542247), real detections reached the browser) |

The ROS 2 smoke test passes in CI on real ROS 2 Jazzy/DDS. In a local
interpreter without ROS 2, `verify.sh` still reports it as **NOT VERIFIED HERE**;
that local result does not invalidate the separate CI evidence.

Learning milestones (Python fluency, math primer, ROS 2 tutorials) are
deliberately not tracked as rows anymore: under the fine-tune-first plan they
are learned just-in-time, and their evidence is simply the Phase 1-2 artifacts
below working.

### Phase 1 — Demo dataset (LeRobot)

| Milestone | Proof | Command | Status |
| --- | --- | --- | --- |
| v0 task spec written (scaled to rig payload) | one-paragraph spec committed under `research-notes/` | n/a | NOT VERIFIED |
| 50+ clean demo episodes recorded | dataset on the Hub (private ok) + episode count + visualization screenshot in `research-notes/log.md` | n/a (record with `lerobot-record`) | NOT VERIFIED |
| Dataset sanity-checked | garbage episodes deleted; camera keys/task wording consistent | n/a | NOT VERIFIED |

### Phase 2 — Fine-tuned policy (LeRobot)

| Milestone | Proof | Command | Status |
| --- | --- | --- | --- |
| Fine-tuning run completed (ACT baseline) | training config + checkpoint pushed to the Hub, run note in `research-notes/log.md` | `lerobot-train --policy.path=... --dataset.repo_id=...` | NOT VERIFIED |
| Policy evaluated on the bench | ≥20 rollout episodes with success rate; the number, not a best-of clip | `lerobot-record --policy.path=<checkpoint>` (eval mode) | NOT VERIFIED |
| ≥70% success on v0 task | eval record + raw bench video in `research-notes/log.md` | re-run the eval | NOT VERIFIED |

Evidence discipline (carried over from the retired sim proofs): record the
dataset version, training config, checkpoint hash, eval episode count and
success rate per run. A video alone is not evidence — anyone can cherry-pick a
clip. The reproducible eval is the evidence.

### Phase 3 — Deploy, harden & iterate on the robot

| Milestone | Proof | Status |
| --- | --- | --- |
| Policy runs standalone on the arm | camera → policy → servos loop at usable control frequency; run note + bench video | NOT VERIFIED |
| Policy runner wrapped as a ROS 2 node | a `tools/arm_smoke_test.py`-style probe (mirroring `ros2_smoke_test.py`): command one safe motion, assert joint state changed | NOT VERIFIED |
| Robustness pass (lighting/variation/transforms) | before/after eval numbers under varied conditions | NOT VERIFIED |
| Teleoperation fallback | the viewer/dashboard's CALL SUPPORT path exercised on real hardware, with the intervention recorded | NOT VERIFIED |
| Multi-minute repetition video | one take, including failures and recoveries | NOT VERIFIED |

Physical milestone proofs are *not* automatable — they are recorded evidence with
a defined format. Define the format before you need it: continuous take, visible
clock, intervention log exported from the dashboard, and the checkpoint
commit of the policy shown on screen.

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

Current evidence (the base Python here has no ROS 2; the ROS 2 rows rest on
public CI runs):

| proof | transport | status |
| --- | --- | --- |
| Cloud ROS 2 in CI (`ros2` job, milestone proof) | (ros2) | **PASS** (run 37474982123) |
| Cloud ROS 2 browser path (`ros2_viewer_check.sh`) | (ros2) | **PASS** ([run 37490542247](https://github.com/johnopaluwa/robo-rl/actions/runs/37490542247)) |
| Codespaces devcontainer suite | (ros2) | **READY — runs on create** |
| unit tests | python 3 | **PASS** |
| tools contract + regression tests | python 3 | **PASS** |
| pipeline logic proof (16 checks) | (sim/viewer) | **PASS** |
| live viewer + WebSocket command round-trip | (sim/viewer) | **PASS** |
| Phase 0: niche chosen in README | docs | **PASS** |
| Phase 0: 5 customer conversations | docs | **PENDING (0/5)** |
| Phase 0: demo rig ordered & teleoperating | physical | **NOT VERIFIED** (no arm yet) |
| Phase 1: 50+ demo episodes on the Hub | physical | **NOT VERIFIED** |
| Phase 2: fine-tuned policy, ≥70% bench success | physical | **NOT VERIFIED** |
| ROS 2 in the local interpreter | (ros2) | **NOT VERIFIED HERE**; real-DDS CI evidence above remains PASS |

**Retired (2026-10-06):** the RL-from-scratch proofs (MuJoCo tray env +
domain randomization tests, scripted-transfer demo, stock Pendulum PPO
baseline, custom-task PPO debug run) were removed with the `simulation/`
stack. Their final record — environment PASS, learned policy 0/3 on a short
debug run — is preserved in git history under the tag
`pre-pivot-rl-from-scratch`. Nothing on the current path inherits their
credibility.

Nothing here can tick a hardware milestone. That is the point of the table.

## How to read the CI history

**The Actions run list is a log, not a status.** Every past run keeps its own
verdict forever, so a healthy project still shows a column of red ❌ from the
commits where things were broken. Only the newest run says anything about the
current code.

Where to look, in order of usefulness:

1. **README badge** — the newest run on the default branch. Green means current.
2. **PR "Checks" tab** — the latest verdict per job for the PR's head commit.
3. **The newest row in the run list** — the top entry, not the ones below it.
4. Any red run older than the newest commit is history. Click it if you want the
   story; it will not change.

Being honest about this matters more than looking tidy: the red runs below are
where the seven real bugs in the next section were found. Deleting them to make
the page look better would be exactly the "screenshot instead of evidence"
behaviour this file exists to prevent. If you want a genuinely clean board, use
`gh run delete` sparingly and always after the fix is merged — never to hide a
failure that is still live.

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
5. Tick the box in `docs/ROADMAP.md` only when the script passes on the machine
   that has the real thing (ROS 2 box, arm, customer site).

## Gaps in this system (known, deliberate)

- **`artifacts/` is gitignored.** Proofs are reproducible, not committed, so
  nothing rots. If you want a proof in the repo, commit the script that
  regenerates it, not the output.
- **The Codespaces devcontainer has not been executed yet.** CI has (green
  runs above); the devcontainer's first run in Codespaces is still its real
  test. That is stated here rather than hidden: an unverified claim should be
  visible, and a red run is information.
- **`colcon test` is deliberately not in CI.** The package's tests are run
  directly by `verify.sh` under the ROS 2 environment; wiring `colcon test` adds
  a pytest dependency that could not be verified from here. Add it once you can
  watch it run.
- **The viewer's grasp model is a teaching model**, not a policy: the sim-mode
  grasp is a probability curve, not physics and not a learned policy. It exists
  so the confidence/threshold trade-off is visible, and it is labelled as such
  in the code and the UI.
- **Phase 1-2 proofs are not automatable from this repo.** Demo datasets and
  fine-tune/eval runs happen in the LeRobot stack on real hardware; their
  evidence format (dataset version, config, checkpoint, eval numbers) is
  defined in the registry above so it is recorded the same way every time.
