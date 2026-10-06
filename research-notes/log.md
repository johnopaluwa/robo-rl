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
