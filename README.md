# robo-rl

[![verify](https://github.com/johnopaluwa/robo-rl/actions/workflows/verify.yml/badge.svg)](https://github.com/johnopaluwa/robo-rl/actions/workflows/verify.yml)

**Mission:** Go from Angular/frontend engineer → RL-robotics founder, by building a
pick-and-sort robot (warehouse / recycling / food) that can get a real paying
customer, on a **heavy part-time schedule (15-20 hrs/week)** and a
**$1,000-5,000 self-funded budget**.

This repo is the working home for that project: the plan, the learning log,
the simulation code, the ROS 2 workspace, and the Angular fleet/control
dashboard that is your unfair advantage.

**Current task:** not selected yet. Use the Phase 0 customer-discovery
conversations to choose one narrow, evidence-backed task before specializing
the simulation or buying hardware. Capture conversations with the
[interview template](research-notes/customer-discovery-template.md).

## Start here — and see it actually work

```bash
./tools/verify.sh              # run every proof that works without ROS 2
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

1. **[docs/ROADMAP.md](docs/ROADMAP.md)** — the 18-month plan, phase by phase.
2. **[docs/MILESTONES.md](docs/MILESTONES.md)** — the checkbox tracker. Update this weekly.
3. **[docs/VERIFICATION.md](docs/VERIFICATION.md)** — **how each milestone gets proved**, and what each proof does *not* cover.
4. **[docs/ROS2_ANYWHERE.md](docs/ROS2_ANYWHERE.md)** — free ways to run real ROS 2 in the cloud (Codespaces, Actions) and the dead ends (RoboMaker).
5. **[docs/SKILLS_CHECKLIST.md](docs/SKILLS_CHECKLIST.md)** — what to learn, in what order, with resources.
6. **[docs/TECH_STACK.md](docs/TECH_STACK.md)** — exact tools/hardware to buy and install, fit to your budget.
7. **[docs/BUSINESS_PLAN.md](docs/BUSINESS_PLAN.md)** — how to get a real pilot customer and, later, raise money.

**The rule this repo runs on:** no milestone is "done" until you can re-run a
command and see the same result. Simulation results are labelled `(sim)` and can
never claim a ROS 2 or hardware milestone — `tools/verify.sh` prints a table that
says exactly which claims are verified, and which are not.

## Repo layout (fills in as you build)

```
robo-rl/
├── docs/                 # roadmap, business plan, proof registry — read this first
├── simulation/           # MuJoCo / Isaac Sim envs, reward functions, training scripts
├── ros2_ws/              # ROS 2 packages: drivers, perception, policy runner
├── web/                  # live viewer + prototype of the Phase 4 dashboard
├── tools/                # verify.sh and the proof scripts it orchestrates
├── .devcontainer/        # free real-ROS 2 dev environment (Codespaces)
├── .github/workflows/    # CI that proves the ROS 2 path on every push
├── dashboard-angular/    # the fleet/teleoperation dashboard (your edge)
└── research-notes/       # notes on papers, courses, failed experiments, customers
```

## The one-sentence strategy

Don't try to become a world-class RL researcher first — become a **system
integrator** who stitches together existing open-source sim tools, cheap
hardware, and a great Angular UI fast enough to get a real business sorting
*one* specific thing for *one* real customer, then let that revenue + data
pull you forward.
