# Tech Stack & Shopping List ($1,000–$5,000 budget)

Principle: spend on the arm + sensors + GPU-hours, not on anything custom.
Everything here is off-the-shelf or free/open-source.

**The strategy this serves** ([ROADMAP.md](ROADMAP.md)): fine-tune a
pretrained policy on teleoperated demos with LeRobot, deploy early, iterate.
So the shopping list is bought in **Phase 0**, not Phase 3 — demos need the
real arm from week one.

## Software (free/open-source)

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.12+ (LeRobot v0.6+ requires it); keep Angular/TS for the dashboard | Standard for ML/robotics |
| Imitation/VLA stack | **LeRobot** (Hugging Face) — `lerobot-teleop`, `lerobot-record`, `lerobot-train`, `lerobot-eval` | Purpose-built for low-cost arms: teleop → dataset → fine-tune → deploy is one documented pipeline |
| Policy (start) | **ACT** (fine-tune a pretrained checkpoint) | Fast, best default for precise single-task manipulation; trains on modest GPUs |
| Policy (step-up) | **SmolVLA** (`lerobot/smolvla_base`, ~450M params) | Language-conditioned VLA that fine-tunes on a single 8 GB GPU in hours; try it when ACT plateaus |
| Policy (later, data-hungry) | π0 / π0.5 (OpenPI, via LeRobot) | Long-horizon, dexterous tasks; needs far more data than you'll have at first |
| Datasets & checkpoints | Hugging Face Hub (private repos, free) | Versioned datasets/checkpoints; `lerobot-record` pushes straight there |
| Middleware | ROS 2 (Jazzy LTS) | Phase 3: policy runner as a node; hardware integration; already proved in this repo's CI |
| Bridge | `rosbridge_suite` (WebSocket, ROS 2 ↔ browser) | Phase 4: lets Angular talk to ROS 2 without leaving your stack |
| Frontend | Angular + RxJS | Phase 4 dashboard/teleop UI — your edge |
| Compute | Your laptop/PC for teleop + recording (CPU is fine); **rented cloud GPU** for fine-tuning — RunPod, Vast.ai, Lambda Labs, or Hugging Face Jobs | Don't buy a GPU. ACT/SmolVLA fine-tuning fits an 8 GB card (RTX 4060/3090 class, ~$0.30-0.70/hr) |

**RL (for later, if ever):** LeRobot also ships RL support — the plan is to
use it only as a refinement step once demo-collection stops improving the
policy, never as the from-scratch entry point (that path was tried and
retired; see the tag `pre-pivot-rl-from-scratch`).

## Where compute happens: the data → train → deploy loop

No standing service, nothing runs 24/7. Each step runs where it is cheapest:

| Step | Tool | Runs on | Cost |
|---|---|---|---|
| Teleoperate + record demos | `lerobot-teleop`, `lerobot-record` | bench laptop (CPU is fine) | free |
| Dataset + checkpoint storage | Hugging Face Hub (private repos) | — | free |
| **Fine-tune** | `lerobot-train` | **a rented GPU, by the hour** — or your own ≥8 GB NVIDIA GPU | ~$0.15–0.70/hr |
| Evaluate on the bench | `lerobot-record --policy.path=...` | bench laptop | free |
| Deploy on the arm | policy inference loop | bench laptop / mini PC tethered to the arm | free |

GPU access, in order of preference:

1. **Your own NVIDIA GPU (≥8 GB VRAM)** — if you have one, there is no
   service at all: `pip install "lerobot[training,smolvla]"` and train
   locally. (Apple Silicon can train small ACT configs on MPS, but slowly —
   renting is the sane default for a MacBook.)
2. **Vast.ai / RunPod** — 2026 medians: RTX 3090 ≈ $0.15/hr, RTX 4090 ≈
   $0.35–0.70/hr. Rent for the hours a run takes, destroy the pod afterwards.
   LeRobot resumes from checkpoints (`--resume=true`), so an interruptible
   spot box is annoying, not fatal.
3. **Hugging Face Jobs** — the tightest integration: your dataset and
   checkpoints already live on the Hub, so you submit the same training
   config and pay per minute (GPUs from ~$0.40/hr). Zero infrastructure.

What a run actually costs: ACT on 50–150 demos ≈ **1–3 GPU-hours** (well
under $1.50); SmolVLA for 20k steps ≈ 4–8 hours on a 4090 (**$2–4**). A full
Phase 2 of iterating is therefore *tens of dollars* — the $100–300 GPU line
in the budget below covers 50+ experiments. (ACT is small enough that
training it fresh on your demos is equally routine — hours, not days; the
pretrained-start matters most for SmolVLA/π0.)

Deployment is always local — inference is far cheaper than training. ACT
runs comfortably on a laptop CPU at SO-101 control rates; if SmolVLA becomes
the keeper, a used Jetson Orin or a mini PC with a small GPU is the Phase 3
upgrade. Still no ongoing cloud bill.

## Where MuJoCo went (and when sim comes back)

MuJoCo is **not on the critical path anymore**. RL-from-scratch needed
millions of simulated attempts; imitation learning needs 50–100 *real*
teleoperated episodes — the demo dataset replaces the simulator. (The retired
stack lives under the git tag `pre-pivot-rl-from-scratch`.)

Sim retains two optional uses later:

- **Config pre-flight** — debug a `lerobot-train` config on one of LeRobot's
  built-in sim environments (Aloha, PushT, community SO-101 MuJoCo envs)
  before spending bench time or GPU hours.
- **RL refinement** (Phase 3, optional) — if demo collection stops improving
  the policy, LeRobot's RL support can refine against the task in sim.

## Hardware (buy in Phase 0 — this IS the path now)

| Item | Example options | Approx. cost |
|---|---|---|
| Robot arm pair | **SO-ARM100/SO-101 leader + follower kit** — WowRobo SO-ARM101 (~€430-530, incl. camera), Seeed SO-ARM101 motor kit (~€350, add 3D-printed parts), or self-sourced STS3215 servos + printed frame (~$150-250). SO-101 is the LeRobot community default in 2026 with first-class config support | $200 – $550 |
| Cameras | 2× USB webcams (e.g. Logitech C920/C922) — one over-the-shoulder, one side/wrist view; kits often include one | $0 – $140 |
| Spares | 1-2 spare STS3215 servos, spare gripper parts | $30 – $60 |
| Mounting/rig | Table clamps (usually included), camera stands, 3D-printed fixtures (makerspace/library if you don't print) | $30 – $100 |
| Task props | Scaled trays/sheets + marker targets for the v0 task (see payload note below) | $20 – $50 |
| Power & cables | Supplied PSU + powered USB hub (2 cameras + 2 arms on one bus is asking for brownouts) | $20 – $50 |
| Compute buffer | Cloud GPU credits for fine-tuning runs | $100 – $300 |
| Contingency | Shipping/duties, mistakes | $100 – $200 |

**Recommended starter combo:** a SO-ARM101 leader-follower kit with camera
(~€450) + one extra webcam (~$70) + powered USB hub + props (~$50) + GPU
credits ($150) ≈ **$800-900 total** — comfortably inside even the low end of
the budget, with the rest held for the Phase 3 scale-up decision.

### Payload reality check (read before buying anything bigger)

SO-ARM100/101 lifts roughly **200-250 g**. A full-size 60×40 cm bakery tray
is heavier than that *empty*. This is deliberate, not a mistake:

- v0 task (Phases 1-2) is a **scaled-down** tray/sheet transfer — the goal is
  to prove the *loop* (demos → fine-tune → deploy → iterate), not the final
  payload.
- Once the loop works and the interviews confirm the niche, the Phase 3
  decision point is: real tray format → step up to an arm like the
  Elephant Robotics myCobot 280 (~$1,500-2,000) or UFACTORY Lite 6
  (~$2,000-3,000), funded from remaining budget/pilot revenue.
- Don't buy the bigger arm before that decision has real data behind it.

## What NOT to buy (yet)

- **No dedicated workstation GPU** — rent by the hour; fine-tuning fits small
  cloud cards.
- **No industrial cobot** (UR, ABB, Fanuc) — lease/finance only after a
  paying pilot.
- **No custom PCBs/electronics** — stock controllers, stock cameras.
- **No depth camera yet** — a RealSense D435/D455 ($300-450) joins in Phase 3
  *if* the task turns out to need depth; 2 plain webcams are what ACT/SmolVLA
  fine-tunes in the LeRobot community consume happily.
- **No second arm type** "to compare" — one rig, one task, until it works.
