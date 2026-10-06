# The 18-Month Roadmap: Angular Dev → RL Robotics Founder

**Your constraints (locked in):**
- Time: ~15-20 hrs/week (heavy part-time, around your current job)
- Budget: $1,000-5,000 self-funded before seeking outside money
- Niche: picking / sorting (warehouse, recycling, or food — to be narrowed in Phase 0)
- Background: Angular, TypeScript, RxJS, component architecture — all genuinely reusable

**Why 18 months, not 12:** the aggressive 12-month plan assumes full-time (~35-40
hrs/wk). At 15-20 hrs/wk you have ~45-55% of that throughput, so the same
milestones realistically take ~1.5-1.8x longer. 18 months is the honest
version of the same plan. If you land a paying pilot or raise a small
pre-seed partway through and can go full-time, you can compress the back half
significantly — treat the dates below as a budget, not a promise.

**Weekly rhythm (apply every week, every phase):**
- ~70% building/learning (hands-on, not just watching courses)
- ~15% customer discovery / talking to real business owners in your niche
- ~15% writing it down (research-notes/, a public build log, or X/LinkedIn posts)
  — this becomes your fundraising and recruiting material for free.

---

## Phase 0 — Niche Lock & Groundwork (Weeks 1-4)

**Goal:** stop having an "idea" and start having a specific, falsifiable target.

- [ ] Pick ONE narrow task inside picking/sorting. Examples to choose from:
  - Sorting a single recyclable stream (e.g. separating PET bottles from mixed recycling)
  - Picking one SKU type out of a bin for a small e-commerce fulfillment shop
  - Loading/unloading trays in a small bakery or co-packing line
  - Sorting defective vs. good parts on a small manufacturing line
- [ ] Talk to 5 local business owners/facility managers in that space this month
      (see [BUSINESS_PLAN.md](BUSINESS_PLAN.md) for the script). You are not selling
      yet — you're validating that the pain is real and finding out what "good
      enough" looks like to them.
- [ ] Set up your dev environment: Python 3.11+, VS Code, `uv` or `conda`,
      a GitHub habit of committing weekly.
- [ ] Start `research-notes/log.md` — a running diary. Future-you (and future
      investors) will want this.

**Exit criteria:** one sentence you can say out loud — *"I'm building a robot
that sorts X at Y type of business, because Z."*

---

## Phase 1 — The Core Tech Pivot: Python, Math, ROS 2 Mental Model (Months 1-4)

**Goal:** become dangerous in Python and understand robot software architecture,
by mapping it onto what you already know from Angular.

- [ ] Python fluency: data structures, NumPy, basic OOP, async if needed.
      (If you can write a service in Angular/TS, this is ~2-3 weeks of focused work.)
- [ ] Math refresher, applied not theoretical: linear algebra (vectors, matrices,
      transforms), basic probability, just enough calculus to read a loss function.
      Don't aim for a math degree — aim to not be scared of an equation in a paper.
- [ ] Learn ROS 2 basics by analogy:
  - ROS 2 **node** ≈ an Angular **service/component** — a self-contained unit with inputs/outputs
  - ROS 2 **topic** (pub/sub) ≈ an **RxJS Observable** — async streams multiple nodes subscribe to
  - ROS 2 **service call** ≈ an Angular **HTTP request** — request/response, not streaming
  - ROS 2 **action** ≈ a **long-running task with progress + cancel**, like a file upload with a progress bar
- [ ] Build one toy ROS 2 package: a fake "camera" node publishing random
      "detected object" messages, and a "picker" node that subscribes and logs
      what it would do. This is just plumbing practice — no AI yet.
- [ ] Install and poke at PyTorch: tensors, a basic training loop on MNIST or similar.

**Exit criteria:** you can write a ROS 2 publisher/subscriber pair from memory
and explain it to someone else using the Angular analogies above.

---

## Phase 2 — Simulation MVP: Train a Virtual Robot to Sort (Months 5-9)

**Goal:** a simulated arm that reliably does *your* chosen task, with zero
physical hardware risk yet.

- [ ] Pick your simulator: **MuJoCo** (free, lighter weight, great docs, good
      first choice given your budget/GPU constraints) or **NVIDIA Isaac
      Sim** (heavier, needs a decent GPU or cloud instance, more realistic
      rendering/physics — revisit this once Phase 2 is underway).
- [ ] Don't write an RL algorithm from scratch. Use a maintained library:
      **Stable-Baselines3** (simpler, great for one person) or **Ray RLlib**
      (more scalable, steeper learning curve). Start with SB3.
- [ ] Build (or adapt an existing) gym-style environment that mimics your task:
      objects spawn in a bin/tray, arm has a gripper, reward = successfully
      sorted item in correct destination, penalty = drop, collision, timeout.
- [ ] Also seriously evaluate **imitation learning / VLA fine-tuning** as a
      shortcut instead of pure RL-from-scratch — this is what most 2025/2026
      real-world manipulation startups actually do:
  - Look at **LeRobot** (Hugging Face) — open-source stack built exactly for
    low-cost arms, with pretrained policies (ACT, diffusion policy) you can
    fine-tune on a small number of human-teleoperated demonstrations, then
    optionally refine with RL. This can get you a working policy *much*
    faster than training RL from a blank slate.
  - Pure RL is best reserved for the specific sub-skill that needs robustness
    (e.g. fine force/grip adjustment) once you have a baseline behavior.
- [ ] Implement **domain randomization**: randomize object position/size/
      color/friction/lighting in sim so the policy doesn't overfit to a
      perfect simulated world. This is the single highest-leverage thing you
      can do to survive the sim-to-real jump later.
- [ ] Use Claude (or any strong coding LLM) throughout this phase as your
      pair programmer: generating env boilerplate, reward function drafts,
      explaining training curves, debugging PyTorch shape errors. You still
      own the judgment calls — it can't tell you if a policy is actually safe
      or sensible in the physical world.

**Exit criteria:** a video of a simulated robot completing your task
successfully >80% of the time across randomized conditions, saved to
`simulation/` with the training config checked in.

---

## Phase 3 — Physical Hardware Integration (Months 10-14)

**Goal:** the same behavior, now running on a real, cheap robot arm.

- [ ] Hardware shopping list fit to your $1,000-5,000 budget — see
      [TECH_STACK.md](TECH_STACK.md) for specific models and prices. Budget
      roughly: $600-2,000 for the arm, $300-500 for a depth camera, $0-500 for
      a basic gripper/end-effector, keep the rest as buffer/compute credit.
- [ ] Get the arm talking to ROS 2 (most hobbyist/desktop arms today have a
      community ROS 2 driver or a Python SDK you wrap in a ROS 2 node).
- [ ] Build the perception pipeline: depth camera → object detection/
      segmentation (a pretrained model is fine here, e.g. a lightweight
      YOLO or Segment Anything variant) → pose estimate → feed into policy.
- [ ] Transfer your simulated policy to the real arm. It will not work
      perfectly on day one — budget real time here for:
  - Recalibrating camera-to-robot coordinate transforms
  - Retuning for real sensor noise and latency
  - Possibly collecting a small set of real demonstrations to fine-tune
    (this is normal, not a failure — it's literally what "sim-to-real gap"
    means in practice)
- [ ] Build in a **safety/teleoperation fallback** from day one: if the
      policy's confidence is low, pause and let a human (you) take over via
      a simple manual control. This isn't cheating — it's how real pilots
      ship (see the "Wizard of Oz" approach in BUSINESS_PLAN.md).

**Exit criteria:** a raw, unedited, multi-minute video of the physical robot
completing your task repeatedly in your own workspace, including some
failures and recoveries (investors and customers trust this far more than a
polished highlight reel).

---

## Phase 4 — The Angular Dashboard & First Pilot (Months 15-18)

**Goal:** package the system as something a non-technical business owner can
trust and use, and get it into a real site.

- [ ] Build the fleet/control dashboard in Angular — this is where your
      existing expertise pays off directly:
  - Live camera feed + overlay of what the model "sees"
  - Model confidence / status indicator
  - Three big buttons for the customer: **START**, **STOP**, **CALL SUPPORT**
  - A private/advanced view for you: policy logs, intervention history,
    success/failure counts, latency — this is your debugging and data-
    collection cockpit
  - Use WebSockets (or a ROS 2 bridge like `rosbridge_suite`) to stream data
    from the robot's Python/ROS 2 stack into the Angular frontend in
    real time — directly analogous to the RxJS streams you already build.
- [ ] Run your first 2-week, zero-risk, free pilot at one real business (see
      BUSINESS_PLAN.md for the exact script and structure).
- [ ] Capture real-world performance data from the pilot and feed it back
      into retraining/fine-tuning the policy (your first "data flywheel" loop).
- [ ] Convert the free pilot into a small paid RaaS contract, even if modest
      (e.g. $500-1,500/month) — a signed contract is worth more right now
      than a bigger number with no commitment behind it.
- [ ] Decide, with real data in hand, whether to self-fund further on
      revenue or raise a pre-seed round (see BUSINESS_PLAN.md, "Funding
      Tiers") to hire your first specialist (an RL/robotics engineer and/or
      a mechatronics engineer) and scale past what one part-time founder can do.

**Exit criteria:** one paying (or committed-to-pay) customer, a working
Angular dashboard, and a real-world video — the package that actually raises
money or sustains itself on revenue.

---

## What to explicitly cut to hit 18 months

- Don't build custom hardware — buy off-the-shelf.
- Don't train a foundation model from scratch — fine-tune an open one.
- Don't aim for full autonomy on day one — teleoperation fallback is fine
  for your first paying customer.
- Don't chase a second task or a second customer type until the first one
  is working end-to-end and generating some revenue signal.
- Don't wait for perfect math understanding before writing code — learn the
  math that a specific error message or paper forces you to learn.
