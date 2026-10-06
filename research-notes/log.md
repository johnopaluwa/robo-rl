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
