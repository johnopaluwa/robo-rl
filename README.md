# robo-rl

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

## Start here

1. **[docs/ROADMAP.md](docs/ROADMAP.md)** — the 18-month plan, phase by phase.
2. **[docs/MILESTONES.md](docs/MILESTONES.md)** — the checkbox tracker. Update this weekly.
3. **[docs/SKILLS_CHECKLIST.md](docs/SKILLS_CHECKLIST.md)** — what to learn, in what order, with resources.
4. **[docs/TECH_STACK.md](docs/TECH_STACK.md)** — exact tools/hardware to buy and install, fit to your budget.
5. **[docs/BUSINESS_PLAN.md](docs/BUSINESS_PLAN.md)** — how to get a real pilot customer and, later, raise money.

## Repo layout (fills in as you build)

```
robo-rl/
├── docs/                 # roadmap, business plan, learning log — read this first
├── simulation/           # MuJoCo / Isaac Sim envs, reward functions, training scripts
├── ros2_ws/              # ROS 2 packages: drivers, perception, policy runner
├── dashboard-angular/    # the fleet/teleoperation dashboard (your edge)
└── research-notes/       # your own notes on papers, courses, failed experiments
```

## The one-sentence strategy

Don't try to become a world-class RL researcher first — become a **system
integrator** who stitches together existing open-source sim tools, cheap
hardware, and a great Angular UI fast enough to get a real business sorting
*one* specific thing for *one* real customer, then let that revenue + data
pull you forward.
