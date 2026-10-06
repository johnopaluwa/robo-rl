# Milestone Tracker

Update this weekly. Check things off as you go — this file is your honest
progress log and doubles as fundraising/pitch material later. Dates are
targets from whenever you start (Week 1 = your actual start date), based on
~15-20 hrs/week.

**Progress note (2026-10-06):** A generic ROS 2 publisher/subscriber example
and standard-library tests now exist under `ros2_ws/src/robo_rl_demo`. Keep the
"Built a toy ROS 2 publisher/subscriber pair" checkbox unchecked until the
package has been built and both nodes have been run in a sourced ROS 2
environment; ROS 2 is not installed in the current development container.

## Phase 0 — Niche Lock & Groundwork (Weeks 1-4)
- [ ] Chosen specific task written down in README.md ("I'm building a robot that...")
- [ ] 5 business owner/facility manager conversations completed, notes in research-notes/
- [ ] Dev environment set up (Python, Git habit, repo structure)
- [x] research-notes/log.md started

## Phase 1 — Python, Math, ROS 2 (Months 1-4)
- [ ] Comfortable writing Python scripts without heavy LLM scaffolding
- [ ] Completed a linear algebra + probability primer
- [ ] Completed official ROS 2 beginner tutorials (CLI + client libraries)
- [ ] Built a toy ROS 2 publisher/subscriber pair from scratch
- [ ] Completed PyTorch 60-minute blitz; trained a basic model end to end

## Phase 2 — Simulation MVP (Months 5-9)
- [ ] Chosen simulator (MuJoCo / Isaac Sim) installed and running a demo env
- [ ] Trained a baseline PPO agent on a stock gymnasium environment (sanity check)
- [ ] Built a custom env matching your real task (objects, bin, reward, failure conditions)
- [ ] Implemented domain randomization (position/friction/lighting/size)
- [ ] (Optional/parallel) Explored LeRobot imitation learning on your task
- [ ] >80% success rate in sim across randomized conditions, video saved

## Phase 3 — Physical Hardware (Months 10-14)
- [ ] Arm + camera purchased and unboxed
- [ ] Arm controllable via ROS 2 / Python SDK ("hello world" move)
- [ ] Perception pipeline: camera → detection/segmentation → pose estimate
- [ ] Sim policy transferred to real arm (first real attempt, even if rough)
- [ ] Teleoperation/manual override fallback implemented
- [ ] Raw, unedited multi-minute video of real robot repeating the task

## Phase 4 — Dashboard & First Pilot (Months 15-18)
- [ ] Angular dashboard: live camera feed, status, START/STOP/CALL SUPPORT
- [ ] rosbridge (or equivalent) connecting ROS 2 stack to the Angular frontend
- [ ] First free 2-week pilot scheduled at a real business
- [ ] Pilot completed, intervention-rate data collected
- [ ] Converted pilot into a paid RaaS contract (even small)
- [ ] Decision made: bootstrap further on revenue, or raise pre-seed

## Longer-term (post month 18)
- [ ] First hire (RL/robotics engineer or mechatronics engineer)
- [ ] Second customer site
- [ ] Data flywheel operating (real-world data → retraining → lower intervention rate)
