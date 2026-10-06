# Phase 2 — MuJoCo tray-loading simulation

The first task model is a bakery tray transfer: move one empty baking tray from
a randomized pickup area on a work table to a randomized drop-off zone. It is an
intentional **learning prototype**, not a digital twin of a particular arm.
MuJoCo simulates the tray, gravity and table contacts. The arm is a Cartesian
position-controlled abstraction, and a successful close uses a virtual grasp
constraint. There is no finger-contact model, camera, oven rack, perception,
ROS 2, or sim-to-real evidence yet.

## Install and prove the simulator

The environment runs headlessly and on CPU; it does not need ROS 2 or a GPU.
Python 3.11+ is recommended.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r simulation/requirements-sim.txt
PATH="$PWD/.venv/bin:$PATH" ./tools/verify.sh --simulation
```

The verification command runs the Gymnasium checker, seven MuJoCo integration
tests (headless diagnostic rendering, reset/step contract, deterministic seeds,
parameter application, grasp, place and drop behavior), and a seeded five-episode scripted transfer. It writes
reproducible JSON/text proofs into the git-ignored `artifacts/proofs/` directory.
The scripted transfer is a simulator smoke test — it is **not** PPO success.

The environment has a headless diagnostic software renderer (top-down and
side-elevation views), so it can record on machines without OpenGL. The committed
`simulation/videos/tray-loading-seed7.mp4` is a short, seeded scripted transfer;
`tray-loading-seed7.json` records the seed, sampled domain values and source
hash. The clip visualizes simulator state but is not a native MuJoCo 3D render
or an RL result. To regenerate it:

```bash
.venv/bin/python -m pip install -r simulation/requirements-video.txt
.venv/bin/python -m simulation.demo_mujoco \
  --seed 7 --episodes 1 --video simulation/videos/tray-loading-seed7.mp4
```

For a GIF, use a `.gif` output path; the MuJoCo install already brings
ImageIO/Pillow. Generated videos and checkpoints are research artifacts; keep
large runs out of Git unless a milestone explicitly needs a small evidence clip.

## Environment contract

`simulation.envs.TrayLoadingEnv` follows the Gymnasium reset/step API and loads
`simulation/envs/assets/tray_loading.xml`.

- **Action:** `dx, dy, dz, gripper` in `[-1, 1]`. Each Cartesian action moves the
tool by at most 2.5 cm; positive gripper action closes it.
- **Observation:** tool position, tray position, target position (metres),
  gripper-closed flag and tray-attached flag.
- **Reward:** small step cost, distance progress, grasp bonus, place success
  bonus; releasing outside the target is a terminal drop penalty.
- **Randomized per reset:** source and target x/y, tray footprint, tray friction,
  and diffuse-light intensity. Exact sampled values are returned in `info` and
  preserved in eval proofs.
- **Seeds:** `reset(seed=N)` reproduces both the observation and all sampled
  domain parameters.

The randomization ranges live in `simulation/domain_randomization.py`; tests
assert that the sampled values vary *and* that the MuJoCo model receives the
sampled size, friction, position and lighting.

## PPO workflow

Install Stable-Baselines3 only when you are ready to train. The default PPO
configuration uses CPU. On a CPU-only machine, installing the CPU PyTorch wheel
first avoids downloading GPU libraries:

```bash
.venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r simulation/requirements-rl.txt

# Sanity-check PPO on a standard Gymnasium continuous-control task.
.venv/bin/python -m simulation.train.train_stock_ppo

# Train the custom environment, then evaluate the exact checkpoint on fixed seeds.
.venv/bin/python -m simulation.train.train_tray_ppo
.venv/bin/python -m simulation.eval \
  --model artifacts/simulation/tray_ppo/model.zip \
  --seed 70 --episodes 100 --min-success-rate 0.80
```

Editable defaults are checked in at `simulation/train/stock_ppo_config.json`
and `simulation/train/tray_ppo_config.json`. Each run records the seed, config
hash, code hash, dependency versions, git state, checkpoint hash (when
applicable), training Monitor log and evaluation metrics under `artifacts/`.
The `eval.py` gate exits non-zero when `--min-success-rate` is not met. A short
smoke run is useful for debugging but is not evidence for the 80% goal.

The stock Pendulum run proves the PPO plumbing only. It says nothing about the
bakery task. The scripted MuJoCo controller proves the scene can run and the
reward/failure path is reachable; it is not a learned policy. Neither result
can tick a ROS 2 or hardware milestone.
