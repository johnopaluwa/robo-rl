# The Roadmap: Fine-Tune First, Then Hardware, Then UI

**Strategy (revised 2026-10-06):** do not train RL from scratch. Do what most
2025/2026 real-world manipulation startups actually do — **fine-tune a
pretrained policy on a small set of human-teleoperated demonstrations** with
[LeRobot](https://github.com/huggingface/lerobot) (Hugging Face), deploy it on
cheap hardware early, and iterate on the real robot until the task is
functional. The Angular dashboard comes last, once there is a robot worth
dashboarding.

The order of operations, locked:

1. **Base model → fine-tune** on teleoperated demos of the task
2. **Deploy on real hardware**; test → retrain → redeploy until functional
3. **Build the UI** around what actually works

This file is the single plan and progress tracker (it absorbed the old
`MILESTONES.md` checkbox tracker and `SKILLS_CHECKLIST.md` resource list — one
plan, one place). The verification rules from
[VERIFICATION.md](VERIFICATION.md) still apply: **no proof, no checkbox**, and
viewer/sim evidence never ticks a ROS 2 or hardware row.

**Your constraints (unchanged):**
- Time: ~15-20 hrs/week (heavy part-time, around your current job)
- Budget: $1,000-5,000 self-funded — roughly $500-800 of it is spent in
  Phase 0 on the demo-collection rig (exact list: [TECH_STACK.md](TECH_STACK.md))
- Niche: bakery tray loading/unloading — a **working hypothesis**, chosen by
  desk research, still pending 5 validation interviews (0/5 recorded)
- Background: Angular, TypeScript, RxJS — your edge for the Phase 4 dashboard,
  and a working mental model for ROS 2 (topic ≈ Observable)

**Why this beats the old plan:** the previous Phase 2 (train PPO from scratch
on a self-built MuJoCo environment) was months of reward-function fiddling
with no transfer guarantee — and it produced a 0/3 debug run before being
abandoned. Fine-tuning ACT or SmolVLA on 50-100 demos routinely yields a
working single-task policy in days on a rented GPU, and the loop
*"collect demos → fine-tune → evaluate → collect more where it failed"* is the
loop you will run forever — including later at customer sites.

**Weekly rhythm (every phase):**
- ~60% hands-on building (teleop, demos, training runs, hardware)
- ~20% customer discovery — the 5 bakery conversations run **in parallel**
  with the build; they can still kill or reshape the task, so don't hide from
  them while the hardware ships
- ~20% writing it down ([`research-notes/log.md`](../research-notes/log.md),
  a public build log) — free fundraising and recruiting material

---

## Phase 0 — Niche Lock & the Demo Rig (Weeks 1-4)

**Goal:** a specific, still-plausible task **and** a teleoperation rig on the
bench. Hardware comes *first* now, because imitation learning needs the real
arm to collect demonstrations — there is nothing to fine-tune without it.

- [x] Chosen task written down in README.md ("I'm building a robot that...")
      *proof:* `./tools/verify.sh` → "Phase 0: niche chosen in README"
      **DONE 2026-10-06:** bakery tray loading — provisional until the 5
      conversations below confirm or kill it.
- [ ] 5 business owner / facility manager conversations recorded
      *proof:* `./tools/verify.sh` → "Phase 0: 5 customer conversations"
      (counts files in `research-notes/interviews/`; use the
      [template](../research-notes/customer-discovery-template.md) and the
      pitch script in [BUSINESS_PLAN.md](BUSINESS_PLAN.md) §2)
- [ ] Demo rig ordered: SO-ARM100/SO-101 **leader-follower pair + 2 webcams**
      (see [TECH_STACK.md](TECH_STACK.md) — ~$300-600)
      *proof:* dated order note + photo in `research-notes/log.md`
- [ ] Arms assembled, calibrated, and teleoperating via LeRobot
      *proof:* `lerobot-teleop` run note + short bench video in `log.md`
- [x] Dev environment: Python 3.12+ (LeRobot v0.6 requires it), Git habit
      *proof:* `./tools/verify.sh` runs green
- [x] `research-notes/log.md` running

**Exit criteria:** the niche sentence still stands (or was honestly changed),
and you can teleoperate the follower arm smoothly with the leader.

---

## Phase 1 — Teleoperate & Collect the First Dataset (Months 1-3)

**Goal:** 50+ clean demonstrations of a scaled-down version of the task, in
LeRobot dataset format, on the Hugging Face Hub.

- [ ] Define the **v0 task** precisely, scaled to the rig's payload
      (SO-ARM100/101 lifts ~200-250 g — so v0 is e.g. "move a small
      tray/sheet from stack A to marker B", not a full 60×40 cm baking tray;
      see the payload reality-check in [TECH_STACK.md](TECH_STACK.md))
      *proof:* one-paragraph task spec committed under `research-notes/`
- [ ] Fix the scene: camera mounts, lighting, table layout. Camera views must
      be identical between demos and deployment — this is the #1 cause of
      "worked in demos, fails standalone"
      *proof:* annotated photo of the rig in `log.md`
- [ ] Record demos with `lerobot-record`; push the dataset to the Hub
      (private repo is fine). Same task wording and camera keys in every
      episode — SmolVLA/ACT consume exactly the interface stored in the dataset
- [ ] 50 episodes recorded and visualized; garbage episodes deleted, not
      averaged away
      *proof:* dataset URL + episode count + a visualization screenshot in
      `log.md`

**Learn, just-in-time (don't pre-study):** Python fluency you don't already
have (NumPy quickstart), the LeRobot docs for your exact robot, and the
Angular→ROS 2 mental model (node ≈ service, topic ≈ Observable, service call ≈
HTTP request, action ≈ long-running task with progress) when Phase 3 arrives.

**Exit criteria:** a replayable, visualized, 50-episode dataset on the Hub —
the single most valuable artifact this project produces.

---

## Phase 2 — Fine-Tune a Pretrained Policy (Months 3-6)

**Goal:** a fine-tuned policy that does the v0 task on the bench, with a
measured success rate.

- [ ] Rent GPU hours (or use HF Jobs — no local GPU needed;
      [TECH_STACK.md](TECH_STACK.md)); fine-tune **ACT** first — fast, best
      default for precise single-task manipulation
      `lerobot-train --policy.path=<pretrained-act> --dataset.repo_id=<you>/<dataset>`
- [ ] Evaluate with rollouts: `lerobot-record --policy.path=<checkpoint>`
      over ≥20 episodes; record the success rate, not a best-of clip
- [ ] If ACT plateaus, fine-tune **SmolVLA** from `lerobot/smolvla_base`
      (~450M-param VLA; fine-tunes on a single 8 GB GPU in hours, understands
      task language). π0/π0.5 only if you later have far more data
- [ ] **Failure-driven data collection:** run evals, list the top failure
      modes, teleop exactly those cases as new demos, retrain, repeat. This
      loop is the product
- [ ] Keep evidence per run: dataset version, training config, checkpoint,
      eval episodes + success rate, in `log.md` (same discipline as
      [VERIFICATION.md](VERIFICATION.md) — a cherry-picked video is not
      evidence)

**Exit criteria:** ≥70% success over 20+ bench episodes, video + numbers
recorded. (80%+ is the pilot-ready bar; don't gold-plate before real-world
data from Phase 3.)

---

## Phase 3 — Deploy, Harden & Iterate on the Robot (Months 6-10)

**Goal:** the same behavior, robust, on the real rig — with a safety fallback
and a ROS 2 spine.

- [ ] Run the policy standalone on the arm (not just in eval harness):
      camera → policy → servos loop, at usable control frequency
- [ ] Wrap the policy runner as a **ROS 2 node** (the pattern already exists
      in [`ros2_ws/`](../ros2_ws/README.md) — thin node wrappers around
      ROS-free logic)
- [ ] Robustness pass: lighting changes, tray/sheet variation, start-position
      variation; recalibrate camera-to-robot transforms; retune for real
      sensor noise and latency
- [ ] **Safety/teleoperation fallback from day one:** low confidence → pause
      and let a human take over (the "Wizard of Oz" approach,
      [BUSINESS_PLAN.md](BUSINESS_PLAN.md) §3). Log every intervention
- [ ] Decide the scale-up path with data in hand: real bakery trays need a
      bigger arm (payload reality-check in [TECH_STACK.md](TECH_STACK.md)) —
      upgrade only when the loop works end-to-end and the niche survived the
      interviews
- [ ] Optional, last: refine with RL (LeRobot supports it) — only once more
      demos stop improving the policy
- [ ] Raw, unedited, multi-minute video of the robot repeating the task,
      **including failures and recoveries**

**Exit criteria:** that video, plus an intervention count exported from the
viewer/dashboard. Investors and customers trust a raw take far more than a
polished highlight reel.

---

## Phase 4 — The Angular Dashboard & First Pilot (Months 10-14)

**Goal:** package the system as something a non-technical business owner can
trust and use, and get it into a real site.

- [ ] Build the fleet/control dashboard in Angular — where your existing
      expertise pays off directly. [`web/`](../web/README.md) is the living
      specification: same snapshot shape, same command schema, same three
      buttons. Port it with `WebSocketSubject` (RxJS maps 1:1 onto topics):
  - Live camera feed + overlay of what the model "sees"
  - Model confidence / status indicator
  - Three big buttons for the customer: **START**, **STOP**, **CALL SUPPORT**
  - A private/advanced view for you: policy logs, intervention history,
    success/failure counts, latency — your debugging and data-collection
    cockpit
- [ ] Connect it via `rosbridge_suite` (ROS 2 ↔ WebSocket), or keep the
      proven `web/server.py` bridge
      *proof:* `python3 tools/ws_probe.py --port 9090 --path /` against the
      live bridge
- [ ] Run the first 2-week, zero-risk, free pilot at one real business
      (exact script and structure: [BUSINESS_PLAN.md](BUSINESS_PLAN.md) §2)
- [ ] Capture pilot performance data and feed it back into fine-tuning —
      the **data flywheel**, now with real-world failure cases
- [ ] Convert the pilot into a small paid RaaS contract ($500-1,500/month is
      a fine start) — a signed contract beats a bigger number with no
      commitment
- [ ] Decide with real data: self-fund on revenue, or raise a pre-seed
      ([BUSINESS_PLAN.md](BUSINESS_PLAN.md) §5) to hire the first specialist

**Exit criteria:** one paying (or committed-to-pay) customer, a working
Angular dashboard, and a real-world video — the package that raises money or
sustains itself on revenue.

---

## What to explicitly cut

- **No RL from scratch.** Fine-tune pretrained policies; RL is a later
  refinement tool, not the entry point.
- **No foundation model from scratch.** Fine-tune an open one (ACT,
  SmolVLA, π0).
- **No custom hardware.** Buy off-the-shelf (SO-ARM100/101 now; a bigger arm
  only after the loop works and the niche is validated).
- **No Angular app before the robot works.** `web/` is the spec; the real
  dashboard is Phase 4.
- **No second task or second customer type** until the first works end-to-end
  with revenue signal.
- **No pre-studying.** Learn the math/tool a specific failure or paper forces
  you to learn, not the other way round.

## Where the old plan went

- `MILESTONES.md` and `SKILLS_CHECKLIST.md` were merged into this file
  (checkboxes live in each phase above; resources appear just-in-time).
- The RL-from-scratch stack (custom MuJoCo tray env, PPO training scripts,
  results, videos — `simulation/`) was **deleted** on 2026-10-06. It is
  recoverable from the git tag `pre-pivot-rl-from-scratch`. Its honest final
  state: environment + domain randomization worked; the learned-policy result
  was 0/3 on a short debug run — evidence that the RL-from-scratch path was
  the wrong bet for one part-time founder.
