# Running ROS 2 in the cloud, for free

Short answer: **there is no "ROS 2 account" to sign up for — but there are two
free ways to run a real ROS 2 machine on the internet**, and both are already
wired into this repo.

## The landscape (checked October 2026)

| Option | Free? | Runs ROS 2? | Good for | Verdict for this repo |
| --- | --- | --- | --- | --- |
| **GitHub Codespaces** | ✅ 120 core-hrs/mo (~60 h on 2 cores) + 15 GB storage, on a personal Free account | ✅ real Ubuntu 24.04 + ROS 2 Jazzy, full internet | interactive work, seeing the viewer in `--mode ros2` | ⭐ **recommended** |
| **GitHub Actions** | ✅ **unlimited minutes for public repos** | ✅ in a ROS 2 container, every push | permanent, public, automatic proof | ⭐ **recommended** |
| **The Construct (ROSDS)** | ⚠️ free tier: 2 GB storage, public "rosjects" only, 3 starter courses | ✅ real ROS 2 in a browser IDE | learning ROS 2 with guided courses | good for *learning*, weak for verifying your own repo |
| **Foxglove** | ✅ free tier | ❌ **visualises** only | inspecting topics/bags of a system already running somewhere | useful later, not a runtime |
| **rosbridge_suite** | ✅ open source | ❌ bridge only | Phase 4 browser ↔ ROS 2 link | a component, not a host |
| **AWS RoboMaker** | ❌ **discontinued 10 Sep 2025** | ❌ | — | dead end; AWS now points at Batch |
| **Google Cloud Robotics Core** | ❌ discontinued | ❌ | — | dead end |
| Own laptop / VM / WSL2 | ✅ | ✅ | everything, long-term | do this too, eventually |

**The trap to avoid:** Foxglove and rosbridge look like "ROS 2 in the browser",
but they only *show* you a robot that is already running somewhere. Something
still has to run the ROS 2 runtime. That something is what these two options give
you.

---

## Option 1 — Codespaces: ROS 2 in your browser ⭐

GitHub builds and runs a container for you, in the browser. `.devcontainer/` in
this repo pins the official `ros:jazzy-ros-base` image, so you get real rclpy,
the `ros2` CLI and colcon with no install step of your own.

**Steps**

1. On GitHub, open this repo → **Code** → **Codespaces** → **Create codespace on
   `<branch>`**. (Or press `.` on the repo page for github.dev — but that is a
   lightweight editor, *not* a container; you need the real Codespaces one.)
2. Wait for the container to build (first time: a few minutes). Setup runs
   `tools/devcontainer_setup.sh` automatically, which builds the package and
   runs `./tools/verify.sh --ros2` — so the **ROS 2 row in the verification table
   turns green in front of you**, and prints the whole table in the terminal.
3. See it live. Port 8000 is forwarded automatically:

   ```bash
   # terminal 1 — real nodes publishing over DDS
   source /opt/ros/jazzy/setup.bash && source ros2_ws/install/setup.bash
   ros2 run robo_rl_demo fake_camera --ros-args -p publish_rate_hz:=5.0

   # terminal 2 — the viewer in real ROS 2 mode
   source /opt/ros/jazzy/setup.bash && source ros2_ws/install/setup.bash
   python3 web/server.py --mode ros2 --port 8000
   ```

   Open the forwarded port 8000 URL. The badge reads **ROS 2 / DDS LIVE**, the
   ROS 2 graph panel shows the *real* `rclpy` graph, and START / STOP / CALL
   SUPPORT publish onto `arm_command` — which the running picker node obeys.

**Cost control:** 120 core-hours/month is ~60 hours on the default 2-core
machine. Stop the codespace when you finish (it also auto-stops after 30 minutes
of inactivity by default) — stopped codespaces stop consuming compute hours.

**Why this beats the alternatives:** it is your own repo, your own commits, your
own tools, on a real machine — not a curated course sandbox you have to
re-upload your work into, and not a vendor that might be shut down next year
(cf. RoboMaker).

---

## Option 2 — GitHub Actions: proof that runs itself ⭐

`.github/workflows/verify.yml` runs two jobs:

| job | what it does |
| --- | --- |
| **logic** | `./tools/verify.sh` on plain Ubuntu — unit tests, pipeline proof, live viewer + WebSocket round-trip, contract tests |
| **ros2** | installs ROS 2 Jazzy (`ros-tooling/setup-ros`), builds the package, runs `./tools/verify.sh --ros2` **and** `./tools/ros2_viewer_check.sh` (real nodes → viewer → browser protocol over live DDS) |

Each job writes the honest verification table into the run's summary page and
uploads the proof artifacts, so the evidence is attached to the run.

**Why this matters strategically:** it makes "the ROS 2 milestone is done"
*independently checkable*. That green check is the difference between "trust my
screenshot" and "click the link". Investors, a future hire, or a customer's
technical advisor can all verify it without installing anything. Put the badge in
your README and your build log:

```markdown
![verify](https://github.com/<you>/robo-rl/actions/workflows/verify.yml/badge.svg)
```

**Cost:** Actions is free and unlimited for **public** repositories. For a private
repo, the Free plan includes 2,000 minutes/month — this workflow is a few minutes
per run, so either way you are fine for a long time.

**Honesty note:** the workflow was written in a container that could not execute
it (no Docker, no ROS 2 there). Its **first run is the real test**. If it is red,
the log says exactly which step failed — that is the system working, not the
system being broken. Two known things to expect on the first run:

- `setup-ros` installs the *desktop* variant, which is slower than needed. If run
  time annoys you, install only `ros-jazzy-ros-base` via apt instead.
- DDS in containers uses UDP on loopback; if a runner ever isolates that, the
  smoke test will say "0 messages received" rather than failing mysteriously.

---

## Option 3 — The Construct, if you want a guided playground today

Sign up at <https://app.theconstructsim.com>, create a *rosject*, and you have a
ROS 2 machine with a web IDE in about two minutes. Free tier limits: 2 GB of
project storage, public projects only, 2 CPUs / 4 GB RAM on the basic config.

Use it for **learning** — it has ROS 2 courses built in and you cannot break
anything. But: it is a separate environment from your repo, so anything you build
there has to be copied back, and its storage/CPU caps make it a poor fit for
running this repo's verification suite as your permanent record. If you use it,
treat it as a classroom, not as the place your proof lives.

---

## What each option actually proves

This is the part that matters, and it is why `docs/VERIFICATION.md` keeps the
tiers separate:

| Where it ran | Proves | Does NOT prove |
| --- | --- | --- |
| Codespaces + ROS 2 | real rclpy pub/sub, real command delivery, real schema on the wire, browser path carries DDS | that it works on *your* laptop; anything about hardware |
| GitHub Actions + ROS 2 | the same, automatically, on every push, publicly | anything about hardware |
| The Construct | you personally can write ROS 2 code | that *your repo's* code runs (unless you clone it in) |
| Foxglove / rosbridge | nothing on their own | they need a runtime elsewhere |
| Your own arm | the real thing: physics, noise, calibration, safety | scaling and reliability over weeks |

**Running ROS 2 in the cloud legitimately ticks the `Built a toy ROS 2
publisher/subscriber pair` milestone** — it is a real ROS 2 runtime with real
DDS, not a simulation of one. It does **not** tick anything hardware-related, no
matter how green the badge is.

---

## Recommended sequence

1. **Today:** push the branch, let the Actions `ros2` job run, look at the
   summary page. If it is green, `docs/ROADMAP.md` can tick the ROS 2 box — with a
   URL as the evidence.
2. **This week:** open a Codespace once and drive the viewer in `--mode ros2` so
   you have *felt* the loop: button → DDS → node → log line.
3. **Then stop touching cloud ROS 2.** It exists to prove the plumbing, not to
   be a workspace. Your Phase 2 (policy fine-tuning) wants a rented GPU box or
   Hugging Face Jobs, and Phases 1-3 need the real arm on a real bench. The
   cloud's job here is done the moment the checkbox is legitimately ticked.
