# Skills Checklist & Resources

Check these off in `MILESTONES.md`, not here — this file is the reference
list. Ordered roughly by when you'll need them (matches ROADMAP.md phases).
Pick ONE resource per row to start — don't collect courses, finish one.

## Already transferable from Angular (don't over-study these, just notice the parallel)
- [x] Component/service architecture → ROS 2 nodes
- [x] RxJS Observables / async streams → ROS 2 topics, sensor data pipelines
- [x] State management (NgRx-style) → robot state machines, policy state
- [x] Building usable UIs → your dashboard advantage over most roboticists

## Phase 1 — Python, Math, ROS 2
- [ ] **Python for programmers** (you already code — just learn syntax/idioms fast):
      "Python for JavaScript Developers" style guides, or just build small
      scripts and let an LLM correct your style.
- [ ] **NumPy basics**: official NumPy quickstart.
- [ ] **Linear algebra, applied**: 3Blue1Brown's "Essence of Linear Algebra"
      (YouTube, visual, fast) — enough to understand vectors/matrices/
      transforms used in robot kinematics.
- [ ] **Probability basics**: enough to read "expected reward" and understand
      a Gaussian policy — StatQuest (YouTube) is a fast, practical source.
- [ ] **ROS 2 official tutorials** (docs.ros.org) — do the "Beginner: CLI
      tools" and "Beginner: Client libraries" tutorials end to end, in Python.
- [ ] **PyTorch 60-minute blitz** (official PyTorch tutorial) — just enough
      to understand tensors, autograd, and a training loop.

## Phase 2 — RL & Simulation
- [ ] **RL fundamentals**: Hugging Face "Deep RL Course" (free, practical,
      uses Stable-Baselines3 directly — very well matched to this roadmap).
- [ ] **Spinning Up in Deep RL** (OpenAI) — denser but excellent reference
      for policy gradients, PPO, etc. when you want to understand *why*.
- [ ] **Stable-Baselines3 docs** — train your first PPO agent on a stock
      `gymnasium` environment before touching your custom task.
- [ ] **MuJoCo documentation + `gymnasium-robotics`** environments — see how
      existing manipulation tasks (e.g. `FetchPickAndPlace`) are built before
      writing your own.
- [ ] **LeRobot (Hugging Face)** — docs + example notebooks for imitation
      learning (ACT, diffusion policy) on low-cost arms. Directly relevant to
      your hardware choice in TECH_STACK.md.
- [ ] **Domain randomization**: read the original OpenAI "Learning Dexterity"
      blog post and the domain randomization sections of any Isaac
      Sim/Isaac Lab tutorial.

## Phase 3 — Hardware & Perception
- [ ] Your chosen arm's official SDK/driver docs (see TECH_STACK.md) — follow
      their "hello world: move the arm" example first.
- [ ] **ROS 2 + camera basics**: `realsense-ros` or equivalent driver docs.
- [ ] **Basic computer vision for pick tasks**: a pretrained object detector
      (e.g. YOLOv8/Ultralytics docs) or segmentation model — you are
      consuming these, not training from scratch, initially.
- [ ] **Classical control basics**: just enough PID to understand why your
      arm overshoots or oscillates — Brian Douglas's control theory videos
      (YouTube) are a good practical primer.

## Phase 4 — Dashboard & Systems Integration
- [ ] **rosbridge_suite** docs — bridging ROS 2 topics to a web frontend over
      WebSockets.
- [ ] Nothing new on the Angular side — this is where you're already the expert.
      Just decide early: raw WebSocket client vs. a small abstraction layer,
      and how you'll visualize camera frames + telemetry efficiently.

## Ongoing / cross-cutting
- [ ] Read 1 robotics/RL paper abstract + intro per week (arXiv cs.RO,
      cs.LG) even if you skip the math — pattern-matching vocabulary over
      time compounds. Use an LLM to explain sections, not to avoid reading.
- [ ] Keep a public build log (X/LinkedIn/blog) — cheap marketing, recruiting,
      and investor material, and keeps you honest about actual weekly progress.
