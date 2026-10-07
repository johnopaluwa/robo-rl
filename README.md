# robo-rl

[![verify](https://github.com/johnopaluwa/robo-rl/actions/workflows/verify.yml/badge.svg)](https://github.com/johnopaluwa/robo-rl/actions/workflows/verify.yml)

**Mission:** Go from Angular/frontend engineer → robotics founder, by building a
pick-and-sort robot (warehouse / recycling / food) that can get a real paying
customer, on a **heavy part-time schedule (15-20 hrs/week)** and a
**$1,000-5,000 self-funded budget**.

**Current task (chosen 2026-10-06):** *I'm building a robot that loads and
unloads baking trays at small and mid-sized bakeries, because that task is
monotonous, physically hard, and the people who do it are increasingly
impossible to hire.*

This is a **working hypothesis, not yet evidence**: it was chosen by desk
research (see the [log entry](research-notes/log.md) for the reasoning and
alternatives considered), and it still goes to the test — **5 conversations
with bakery owners / facility managers** recorded in
`research-notes/interviews/` (use the
[interview template](research-notes/customer-discovery-template.md)). If the
conversations kill this task, change this sentence honestly instead of
building around it. Candidate prospect list:
[research-notes/prospects.md](research-notes/prospects.md).

## The strategy (revised 2026-10-06): fine-tune first, then hardware, then UI

Do what most 2025/2026 real-world manipulation startups actually do — **don't
train RL from scratch.** Fine-tune a pretrained policy
([LeRobot](https://github.com/huggingface/lerobot), Hugging Face: ACT /
SmolVLA) on a small number of human-teleoperated demonstrations collected on a
cheap arm (SO-ARM100/101 leader-follower pair, ~$300-600), deploy on the real
hardware early, and iterate *collect demos → fine-tune → evaluate → repeat*
until the task is functional. The Angular dashboard comes last, packaged
around what actually works. The full plan, with checkboxes and exit criteria:
**[docs/ROADMAP.md](docs/ROADMAP.md)**.

The previous RL-from-scratch approach (custom MuJoCo environment + PPO) was
retired on 2026-10-06 — its honest final state is preserved in git history
under the tag `pre-pivot-rl-from-scratch`.

## Start here — and see it actually work

```bash
./tools/verify.sh              # proofs that need neither ROS 2 nor hardware
python3 web/server.py          # open http://localhost:8000 and watch it decide
./tools/verify.sh --ros2       # on a machine with ROS 2: proves the DDS path
```

The badge above is not decoration: CI installs real ROS 2 Jazzy, builds the
package, and proves that pub/sub, operator commands and the browser-visible data
path all work over real DDS. Click it to see the evidence.

No ROS 2 installed? You do not need to install anything — run a real ROS 2 box in
your browser for free via **GitHub Codespaces** (`.devcontainer/` is ready), or
let **GitHub Actions** prove the ROS 2 path automatically on every push. See
[docs/ROS2_ANYWHERE.md](docs/ROS2_ANYWHERE.md) for the options, their real costs,
and which dead services to avoid.

1. **[docs/ROADMAP.md](docs/ROADMAP.md)** — the plan *and* the progress tracker:
   fine-tune-first phases, checkboxes, exit criteria, and what to explicitly cut.
2. **[docs/TECH_STACK.md](docs/TECH_STACK.md)** — exact hardware to buy (the
   demo rig), software stack, and compute, fit to your budget.
3. **[docs/VERIFICATION.md](docs/VERIFICATION.md)** — **how each milestone gets
   proved**, and what each proof does *not* cover.
4. **[docs/BUSINESS_PLAN.md](docs/BUSINESS_PLAN.md)** — how to get a real pilot
   customer and, later, raise money.
5. **[docs/ROS2_ANYWHERE.md](docs/ROS2_ANYWHERE.md)** — free ways to run real
   ROS 2 in the cloud (Codespaces, Actions) and the dead ends (RoboMaker).

**The rule this repo runs on:** no milestone is "done" until you can re-run a
command and see the same result. Viewer-sim results are labelled `(sim)` and can
never claim a ROS 2 or hardware milestone — `tools/verify.sh` prints a table
that says exactly which claims are verified, and which are not.

## Repo layout (fills in as you build)

```
robo-rl/
├── docs/                 # roadmap, tech stack, business plan, proof registry — read this first
├── ros2_ws/              # ROS 2 packages: the plumbing pattern the policy runner will follow
├── web/                  # live viewer + the specification for the Phase 4 Angular dashboard
├── tools/                # verify.sh and the proof scripts it orchestrates
├── .devcontainer/        # free real-ROS 2 dev environment (Codespaces)
├── .github/workflows/    # CI that proves the ROS 2 path on every push
├── dashboard-angular/    # the fleet/teleoperation dashboard (built last, your edge)
└── research-notes/       # notes on papers, courses, failed experiments, customers
```

## The one-sentence strategy

Don't try to become a world-class RL researcher first — become a **system
integrator** who fine-tunes open pretrained policies on a cheap robot arm,
iterates on real hardware fast, and wraps it in a great Angular UI — good
enough to get a real business sorting *one* specific thing for *one* real
customer, then let that revenue + data pull you forward.
