# Build Log

## Week 1
- Started the robo-rl roadmap.

## 2026-10-06 — ROS 2 plumbing exercise
- Added a ROS-independent detection schema and confidence decision, plus a ROS 2 synthetic camera publisher and picker subscriber under `ros2_ws/src/robo_rl_demo`.
- Added a launch file, build metadata, test coverage, and instructions for the first live ROS 2 run.
- ROS 2 itself (`rclpy`, `ros2`, and `colcon`) is not installed in this development container. The pure-Python tests can run here, but the ROS package build/live node test is still pending; the milestone is intentionally not checked off.
- Phase 0 remains open: no target niche or customer conversations have been recorded in this repo yet. A per-interview notes template is available in this directory.
