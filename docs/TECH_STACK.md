# Tech Stack & Shopping List ($1,000–$5,000 budget)

Principle: spend on the arm + sensor + compute credits, not on anything
custom. Everything here is off-the-shelf or free/open-source.

## Software (free)

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ (keep your Angular/TS for the dashboard only) | Standard for ML/robotics |
| Middleware | ROS 2 (Humble or Jazzy LTS) | Industry-standard robot software bus |
| Simulator | **MuJoCo** (start here) → NVIDIA Isaac Sim later if you need photorealistic perception training | MuJoCo is free, fast, lower hardware requirements; Isaac Sim is heavier but more realistic, better if/when you have cloud GPU budget |
| RL library | **Stable-Baselines3** (start) → Ray RLlib (scale later) | SB3 is the easiest to actually ship something with, solo |
| Imitation/VLA shortcut | **LeRobot** (Hugging Face) | Pretrained policies (ACT, diffusion policy) you fine-tune on a handful of demos — often faster to a working result than RL-from-scratch for manipulation |
| Perception | Pretrained YOLOv8/Ultralytics or Segment Anything variant | Don't train detection from scratch initially |
| Frontend | Angular + RxJS (your existing stack) | Dashboard/teleop UI — your edge |
| Bridge | `rosbridge_suite` (WebSocket bridge ROS2 ↔ browser) | Lets Angular talk to ROS 2 without rewriting your frontend stack |
| Compute | Your existing laptop/PC for dev; **cloud GPU rental** (RunPod, Lambda Labs, Vast.ai, or Google Colab Pro) for heavier training runs | Avoid buying a GPU — renting by the hour is far cheaper at this stage |

## Hardware (buy in Phase 3, not before)

Budget allocation suggestion within $1,000–5,000:

| Item | Example options | Approx. cost |
|---|---|---|
| Robot arm | SO-ARM100 (~$200, very low cost, popular in the LeRobot community) **or** Elephant Robotics myCobot 280 (~$1,500-2,000) **or** UFACTORY Lite 6 (~$2,000-3,000, more industrial-grade) | $200 – $3,000 |
| Depth camera | Intel RealSense D435/D455 | $300 – $450 |
| Gripper/end-effector | Start with the arm's stock gripper; add a basic adaptive/suction gripper later if your task needs it | $0 – $500 |
| Mounting/rig | Basic tripod/table clamp, 3D-printed fixtures (print at a local library/makerspace if you don't own a printer) | $50 – $150 |
| Compute buffer | Cloud GPU credits for training runs | $100 – $500 |
| Contingency | Cables, power supplies, mistakes | $100 – $300 |

**Recommended starting combo on a tight budget:** SO-ARM100 (~$200) +
RealSense camera (~$350) + cloud GPU credits (~$300) leaves most of a
$1,000-2,000 budget as buffer — and SO-ARM100 has first-class support in the
LeRobot ecosystem, which matters more than raw arm payload/precision at the
prototype stage.

If your chosen niche needs more payload/reach/precision (e.g. heavier
warehouse totes), step up to the myCobot 280 or UFACTORY Lite 6 instead, and
trim the contingency buffer.

## What NOT to buy yet
- No industrial cobot (UR, ABB, Fanuc) — save that for after a paying pilot,
  lease/finance it then.
- No dedicated workstation GPU — rent cloud compute instead.
- No custom PCBs/electronics — use the arm's stock controller and off-the-
  shelf cameras/compute (a mini PC or even your laptop tethered is fine
  for a pilot).
