# Milestone Tracker

Update this weekly. Check things off as you go — this file is your honest
progress log and doubles as fundraising/pitch material later. Dates are
targets from whenever you start (Week 1 = your actual start date), based on
~15-20 hrs/week.

**Progress note (2026-10-06, later):** Run `./tools/verify.sh` for the current,
honest status of every row below — and `./tools/verify.sh --ros2` on a machine
with ROS 2 installed. See [VERIFICATION.md](VERIFICATION.md) for how each
milestone is proved and what each proof does *not* cover.

Every checkbox now has a proof attached. Two rules:

1. **Simulation never ticks a ROS 2 or hardware milestone.** The viewer's sim
   mode and the ROS 2 nodes share one logic module
   (`robo_rl_demo/pipeline.py`), but only the real thing can tick a real box.
2. **No proof, no checkbox.** If you cannot re-run a command and see the same
   result, the milestone is not done.

Current verified status (this container has no ROS 2):

| proof | status |
| --- | --- |
| 21 unit tests | PASS |
| pipeline logic proof (16 checks) | PASS |
| live viewer + WebSocket command round-trip | PASS |
| Phase 0: niche chosen in README | PENDING |
| Phase 0: 5 customer conversations | PENDING (0/5) |
| ROS 2 pub/sub + commands | **VERIFIED in CI** (real DDS, see the tick above) |
| browser path carrying live DDS | being fixed (see research-notes/log.md) |

## Phase 0 — Niche Lock & Groundwork (Weeks 1-4)
- [ ] Chosen specific task written down in README.md ("I'm building a robot that...")
      *proof:* `./tools/verify.sh` → "Phase 0: niche chosen in README"
- [ ] 5 business owner/facility manager conversations completed, notes in research-notes/interviews/
      *proof:* `./tools/verify.sh` → "Phase 0: 5 customer conversations" (counts the files)
- [x] Dev environment set up (Python, Git habit, repo structure)
      *proof:* `./tools/verify.sh` runs green
- [x] research-notes/log.md started
      *proof:* `test -s research-notes/log.md`

## Phase 1 — Python, Math, ROS 2 (Months 1-4)
- [x] Built a toy ROS 2 publisher/subscriber pair from scratch
      **VERIFIED 2026-10-06 in CI** on real ROS 2 Jazzy over real DDS:
      [run 37474982123](https://github.com/johnopaluwa/robo-rl/actions/runs/37474982123)
      — `tools/ros2_smoke_test.py` observed real pub/sub traffic, validated every
      payload against the shared schema, and confirmed STOP/START on
      `arm_command` changed the live node's behaviour. This is a real ROS 2
      runtime (Ubuntu 24.04 + Jazzy), not a simulation: see
      [VERIFICATION.md](VERIFICATION.md) tier 4.
- [ ] Comfortable writing Python scripts without heavy LLM scaffolding
      *proof:* `pipeline.py` stays ROS-free, typed, and covered by `unittest`
- [ ] Completed a linear algebra + probability primer
      *proof:* notes in research-notes/ — not mechanically provable, say so honestly
- [ ] Completed official ROS 2 beginner tutorials (CLI + client libraries)
      *proof:* dated entries in research-notes/log.md
- [ ] Completed PyTorch 60-minute blitz; trained a basic model end to end
      *proof:* a training script under simulation/train/ that runs headless

## Phase 2 — Simulation MVP (Months 5-9)
- [ ] Chosen simulator (MuJoCo / Isaac Sim) installed and running a demo env
      *proof:* a repro script + recording under simulation/ (see VERIFICATION.md)
- [ ] Trained a baseline PPO agent on a stock gymnasium environment (sanity check)
      *proof:* training config + log + eval number, all committed
- [ ] Built a custom env matching your real task (objects, bin, reward, failure conditions)
      *proof:* env unit tests, exactly like `test_pipeline.py` does here
- [ ] Implemented domain randomization (position/friction/lighting/size)
      *proof:* a test asserting parameters differ across resets
- [ ] (Optional/parallel) Explored LeRobot imitation learning on your task
      *proof:* a fine-tuning script that runs headless + notes
- [ ] >80% success rate in sim across randomized conditions, video saved
      *proof:* `simulation/eval.py --seed N` reproduces the number; the video is
      supporting evidence, not the evidence

## Phase 3 — Physical Hardware (Months 10-14)
- [ ] Arm + camera purchased and unboxed
      *proof:* photo of the rig + serials in research-notes/log.md
- [ ] Arm controllable via ROS 2 / Python SDK ("hello world" move)
      *proof:* `tools/arm_smoke_test.py` — one safe motion, assert joint state moved
- [ ] Perception pipeline: camera → detection/segmentation → pose estimate
      *proof:* committed test frames + a test asserting known objects are found
- [ ] Sim policy transferred to real arm (first real attempt, even if rough)
      *proof:* raw unedited video + intervention count exported from the dashboard
- [ ] Teleoperation/manual override fallback implemented
      *proof:* CALL SUPPORT exercised on real hardware, intervention recorded
- [ ] Raw, unedited multi-minute video of real robot repeating the task
      *proof:* one continuous take with a visible clock, failures included

## Phase 4 — Dashboard & First Pilot (Months 15-18)
- [ ] Angular dashboard: live camera feed, status, START/STOP/CALL SUPPORT
      *proof:* Angular unit tests + the existing protocol probe; `web/` is the spec
- [ ] rosbridge (or equivalent) connecting ROS 2 stack to the Angular frontend
      *proof:* `python3 tools/ws_probe.py --port 9090 --path /` against rosbridge
- [ ] First free 2-week pilot scheduled at a real business
      *proof:* signed one-page pilot agreement in research-notes/pilots/
- [ ] Pilot completed, intervention-rate data collected
      *proof:* exported CSV + the trend chart (falling intervention rate)
- [ ] Converted pilot into a paid RaaS contract (even small)
      *proof:* redacted signed contract
- [ ] Decision made: bootstrap further on revenue, or raise pre-seed
      *proof:* written memo in docs/ with the numbers behind it

## Longer-term (post month 18)
- [ ] First hire (RL/robotics engineer or mechatronics engineer)
- [ ] Second customer site
- [ ] Data flywheel operating (real-world data → retraining → lower intervention rate)
