# Build Log

## Week 1
- Started the robo-rl roadmap.

## 2026-10-06 — ROS 2 plumbing exercise
- Added a ROS-independent detection schema and confidence decision, plus a ROS 2 synthetic camera publisher and picker subscriber under `ros2_ws/src/robo_rl_demo`.
- Added a launch file, build metadata, test coverage, and instructions for the first live ROS 2 run.
- ROS 2 itself (`rclpy`, `ros2`, and `colcon`) is not installed in this development container. The pure-Python tests can run here, but the ROS package build/live node test is still pending; the milestone is intentionally not checked off.
- Phase 0 remains open: no target niche or customer conversations have been recorded in this repo yet. A per-interview notes template is available in this directory.

## 2026-10-06 (later) — Verification system + live viewer
- Built `web/`: a dependency-free live viewer with a sim transport and a real
  rclpy transport. Both drive the same `robo_rl_demo/pipeline.py`, so the sim is
  evidence about the logic and never claims anything about DDS.
- Extracted shared logic into `pipeline.py` (`CameraSource`, `PickerLogic`,
  command schema); the ROS 2 nodes are now thin wrappers. Unit tests went 6 -> 21.
- Added `tools/verify.sh` (one command, honest summary table),
  `tools/proof_pipeline.py` (16 headless checks + JSON/markdown artifacts),
  `tools/ros2_smoke_test.py` (real DDS check; exit 3 = "not verified here"),
  `tools/ws_probe.py` (independent WebSocket client).
- Added `docs/VERIFICATION.md`: every milestone in MILESTONES.md now has a named
  proof, a command, and an explicit statement of what it does NOT prove.
- Learned the hard way: this container cannot install ROS 2 (anaconda.org,
  packages.ros.org and deb.debian.org are all unreachable; `rclpy` is not on
  PyPI). Hence two modes, and the ROS 2 row staying NOT VERIFIED until a real
  machine confirms it.
- Bugs found by testing the viewer instead of trusting it: the picker was never
  subscribed in sim mode, and objects were registered *after* publishing, so
  decisions could not find their object. Both fixed; both now covered by the
  checks that caught them.

## 2026-10-06 (evening) — Free ways to run real ROS 2 in the cloud
- Investigated whether ROS 2 can be run "in the cloud for free". Findings:
  AWS RoboMaker is discontinued (end of support 2025-09-10) and Google Cloud
  Robotics is gone; Foxglove/rosbridge only *visualise* a runtime, they are not
  one. The two options that actually give a real ROS 2 runtime for free are
  GitHub Codespaces (120 core-hrs/mo, ~60h on 2 cores) and GitHub Actions
  (unlimited minutes on public repos).
- Added `.devcontainer/` (official ros:jazzy-ros-base image, port 8000
  forwarded, runs the verification suite on creation) so a real ROS 2 box is one
  click away, and `tools/devcontainer_setup.sh` to provision + prove it.
- Added `.github/workflows/verify.yml`: a `logic` job (no ROS 2) and a `ros2`
  job that installs Jazzy, builds the package, runs `verify.sh --ros2` and the
  new `tools/ros2_viewer_check.sh`. The ROS 2 claim is now publicly checkable by
  anyone via the badge, instead of resting on a screenshot.
- Added `tools/ros2_viewer_check.sh`: real nodes -> viewer in --mode ros2 ->
  browser WebSocket protocol, asserting the browser really receives live DDS.
- Added `--expect-ros2` to the probe, plus a permanent guard in verify.sh that
  FAILS if `--expect-ros2` ever passes against a simulation. The guard is there
  because the first version of the flag silently did nothing and reported PASS —
  a claim-check that cannot fail is worse than no check.
- Remaining honest caveat: the workflow and devcontainer were written in a
  container without Docker or ROS 2, so their first real run is in CI.

## 2026-10-06 (night) — First real CI run: the milestone is verified
- Pushed the cloud paths. GitHub Actions picked the workflow up on the branch.
- **`Logic proofs` job: PASS** (10s). **`Verify with real ROS 2` step: PASS** —
  which means `tools/verify.sh --ros2` ran on real ROS 2 Jazzy over real DDS and
  every check passed: 21 unit tests, 16 pipeline checks, live viewer + WS
  round-trip, the honesty guard, and `ros2_smoke_test.py` (real pub/sub, schema
  on the wire, STOP/START changing live node behaviour).
  => the "toy ROS 2 publisher/subscriber pair" milestone is now ticked, with a
  public CI run as its evidence. Cloud ROS 2 counts as tier 4: a real runtime.
- **`Verify the browser path carries live DDS data` step: FAIL** — my
  `ros2_viewer_check.sh` failed on its first ever execution. As predicted, an
  untested script finds something. Two responses:
  1. Hardened it: no `producer | grep -q` under `pipefail` (early-exit grep can
     SIGPIPE the producer and flip a successful match into a failed pipeline),
     generator-style readiness loops, and `ROS_LOCALHOST_ONLY=1` so DDS
     discovery stays on loopback instead of relying on multicast across the VM
     interface — the classic cross-process DDS failure in cloud runners.
  2. Made it diagnosable: failures now emit `::error::` GitHub annotations with
     the log tails (readable via `gh run view`), plus `ros2 topic info`,
     `ros2 topic hz` and `ros2 node list` so "DDS is not delivering" can be told
     apart from "our bridge is broken". CI logs and artifacts live on blob
     storage that this sandbox cannot reach, so annotations are the channel.
- Note: `ros2_smoke_test.py` exercises nodes in one process; the viewer check is
  the first *cross-process* DDS test in this repo, which is exactly where it
  broke. That distinction is worth remembering.

## 2026-10-06 (late) — Browser-path check: real cause found
- The PR-comment diagnostics channel paid off immediately. The uploaded
  diagnostics file ended after two lines:
      ROS 2 distro: jazzy
      python: Python 3.12.3, rclpy: /opt/ros/jazzy/lib/python3.12/site-packages/rclpy
  then nothing — no FAIL line, exit code 1.
- Cause: `set -u` plus `source /opt/ros/jazzy/setup.bash` and colcon's generated
  overlay. **ROS 2 / colcon setup scripts are not written for `set -u`**; the
  first unset variable they reference makes bash abort the entire script with
  status 1, printing to stderr only (which lands in the job log, not in the
  diagnostics file). Reproduced locally: exit 1, last note printed, "unbound
  variable" on stderr.
  Fix: relax nounset just around those source lines, and assert the overlay
  exists before sourcing it.
- Honest correction: my earlier hardening (avoiding `producer | grep -q` under
  `pipefail`, and `ROS_LOCALHOST_ONLY=1`) was NOT the cause and would not have
  fixed it. Both are still good practice and stay, but they were guesses —
  recorded here so the log does not credit the wrong fix.
- Also added an EXIT trap that records unexpected exit statuses into the
  diagnostics file, so the next silent abort is visible instead of invisible.

## 2026-10-06 (late, 2) — The browser-path step hung; bounded everything
- After the `set -u` fix, the step still did not complete: it ran 12+ minutes with
  no further output, and `gh run cancel` returned 403 (not permitted for this
  integration), so the runs could not be stopped from here.
- Root cause class: unbounded external calls. `ros2 topic list` and friends talk
  to a discovery daemon and can block indefinitely when that daemon is unhealthy
  -- and a leftover daemon from the `verify.sh --ros2` step earlier in the same
  job is a plausible trigger.
- Fixes, all aimed at making a bad step visible instead of silent:
  * every `ros2` CLI call goes through a `ros2_cli` helper wrapped in `timeout`
    (default 15s), so no call can hang;
  * the daemon is reset before the check (`ros2 daemon stop`);
  * diagnostics are appended as the script progresses, not only on failure, so a
    timeout that kills the script still leaves an explanation behind;
  * the CI step has `timeout-minutes: 8` as a backstop;
  * the workflow gained a `concurrency` group with `cancel-in-progress`, so a new
    push supersedes an in-flight run rather than queueing behind a wedged one.

## 2026-10-06 (late, 3) — Found it: a garbage-collected DDS subscription
- With the hang fixed, CI completed and the PR comment finally showed the full
  picture. The evidence was beautifully contradictory:
    ros2 topic hz /detected_object -> average rate: 5.000   (DDS healthy)
    ros2 node list                 -> /fake_camera /picker /web_viewer
    ros2 topic info                -> Subscription count: 1  (only the picker)
    picker log                     -> receiving and deciding normally
    viewer                         -> published=0 decisions=0, forever
- Cause: **rclpy's `create_subscription()` returns an object that nothing keeps
  alive for you.** My RosTransport stored publishers in a dict but threw away
  the subscription's return value, so Python's GC destroyed the DDS subscription
  while the node itself stayed in the graph. The node listed; the sub did not.
- Fix: hold strong references (`self._subscription_objects`).
- Also: `ros_available()` used `importlib.util.find_spec`, which ignores
  `sys.modules` stubs *and* can report "available" when the real import would
  fail (rclpy links native libraries). Now it imports via
  `importlib.import_module` — more correct, and stubbable.
- Added `tools/test_transport_lifetime.py`: stubs rclpy/std_msgs so this whole
  class of bug is catchable **in seconds, in the sandbox that cannot run ROS 2**.
  Verified the test is not vacuous by reintroducing the bug and watching it fail
  (2 failures), then restoring the fix.
- UI-contract tests now count 14 (10 + 4 new).

## 2026-10-06 (final) — Two more real bugs: a hanging cleanup and a discovery race
- The annotation API finally named it: *"The action 'Verify the browser path
  carries live DDS data' has timed out after 8 minutes."* Meanwhile the PR
  comment from the very same commit showed the check **passing**:
  `decisions=3` — real DDS data HAD reached the viewer, over the browser path.
- Bug A: `cleanup()` ran `wait "$pid"` on `ros2 run` wrappers that ignore
  SIGTERM. An unbounded `wait` blocked forever, so a script that had already
  printed PASS sat there until GitHub killed the step — turning a success into a
  red check. Fix: no `wait` at all; TERM, poll with `kill -0` for 3s, then KILL.
- Bug B: the script probed the viewer the moment HTTP answered, which can be
  0.18s after start. A fresh rclpy node needs a moment to discover the publisher,
  so the probe raced discovery and reported a false failure. Fix: wait until the
  viewer itself reports it has received DDS traffic (up to 30s) before testing
  the browser path; if it never does, fail immediately with the self-test,
  graph.transport and topic info.
- So the earlier "passing" and "failing" runs were the same code at different
  timings, and the failure was in my *harness*, not the pipeline. The lesson to
  keep: a check that can hang or race is a check that lies, in both directions.
