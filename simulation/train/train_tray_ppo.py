"""Train a PPO policy against the custom MuJoCo tray-loading environment.

Install ``simulation/requirements-rl.txt``, run the stock-environment sanity
check, then use::

    python3 -m simulation.train.train_tray_ppo
    python3 -m simulation.eval \\
      --model artifacts/simulation/tray_ppo/model.zip --seed 70 --episodes 100

The default configuration is ``tray_ppo_config.json``. Training completion is
not task success; only the separate seeded evaluator reports success rate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from simulation.envs.tray_loading import TrayLoadingEnv
from simulation.proof_utils import (
    config_hash,
    file_sha256,
    git_commit,
    git_worktree_dirty,
    source_hash,
    write_json,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = Path(__file__).with_name("tray_ppo_config.json")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "simulation" / "tray_ppo"
DEFAULT_PROOF_DIR = REPO_ROOT / "artifacts" / "proofs"


def run_training(
    *,
    seed: int,
    timesteps: int,
    n_steps: int,
    batch_size: int,
    gamma: float,
    max_steps: int,
    device: str,
    output_dir: Path,
    proof_dir: Path,
    quiet: bool = False,
) -> dict:
    if timesteps <= 0 or n_steps <= 1 or batch_size <= 0 or max_steps <= 0:
        raise ValueError("timesteps, batch_size and max_steps must be positive; n_steps > 1")
    if batch_size > n_steps or n_steps % batch_size != 0:
        raise ValueError("batch_size must divide n_steps evenly")
    if not 0.0 < gamma <= 1.0:
        raise ValueError("gamma must be in (0, 1]")

    try:
        import stable_baselines3
        import torch
        from stable_baselines3 import PPO
        from stable_baselines3.common.monitor import Monitor
    except ImportError as error:
        raise RuntimeError(
            "PPO training dependencies are missing; install "
            "simulation/requirements-rl.txt"
        ) from error

    output_dir.mkdir(parents=True, exist_ok=True)
    training_env = Monitor(
        TrayLoadingEnv(max_steps=max_steps), filename=str(output_dir / "training")
    )
    training_env.reset(seed=seed)
    env_source = Path(__file__).resolve().parents[1] / "envs" / "tray_loading.py"
    model_source = env_source.parent / "assets" / "tray_loading.xml"
    randomization_source = Path(__file__).resolve().parents[1] / "domain_randomization.py"
    config = {
        "algorithm": "PPO",
        "environment": "simulation.envs.tray_loading.TrayLoadingEnv",
        "policy": "MlpPolicy",
        "seed": seed,
        "requested_timesteps": timesteps,
        "n_steps": n_steps,
        "batch_size": batch_size,
        "gamma": gamma,
        "device": device,
        "max_episode_steps": max_steps,
        "domain_randomization": True,
        "stable_baselines3_version": stable_baselines3.__version__,
        "torch_version": torch.__version__,
        "environment_source_hash": source_hash(
            Path(__file__).resolve(),
            env_source,
            model_source,
            randomization_source,
            Path(__file__).resolve().parents[1] / "proof_utils.py",
        ),
    }
    model = PPO(
        "MlpPolicy",
        training_env,
        seed=seed,
        n_steps=n_steps,
        batch_size=batch_size,
        gamma=gamma,
        device=device,
        verbose=0 if quiet else 1,
    )
    config["resolved_device"] = str(model.device)
    fingerprint = config_hash(config)
    try:
        model.learn(total_timesteps=timesteps, progress_bar=False)
        actual_timesteps = int(model.num_timesteps)
        checkpoint = output_dir / "model"
        model.save(str(checkpoint))
    finally:
        training_env.close()

    metrics = {
        "proof": "custom-tray-ppo-training",
        "verdict": "PASS",
        "transport": "MuJoCo + Gymnasium (simulation only)",
        "seed": seed,
        "config_hash": fingerprint,
        "episodes": None,
        "success_rate": None,
        "requested_timesteps": timesteps,
        "actual_timesteps": actual_timesteps,
        "checkpoint": str(checkpoint.with_suffix(".zip")),
        "checkpoint_sha256": file_sha256(checkpoint.with_suffix(".zip")),
        "training_log": str(output_dir / "training.monitor.csv"),
        "git_commit": git_commit(),
        "git_worktree_dirty": git_worktree_dirty(),
        "proves": [
            "Stable-Baselines3 PPO completed the configured custom-environment training run",
            "the environment randomizes tray position, target position, friction, size and lighting",
        ],
        "does_not_prove": [
            "the trained policy meets the >80% randomized-condition evaluation target",
            "physical gripper contact, perception, or sim-to-real transfer",
            "any ROS 2 or physical-hardware milestone",
        ],
    }
    write_json(output_dir / "config.json", config)
    write_json(output_dir / "training.json", metrics)
    write_json(proof_dir / "tray_ppo_training.json", metrics)
    if not quiet:
        print(
            f"PPO tray training: {actual_timesteps} timesteps "
            f"(seed={seed}, randomized MuJoCo scenes)"
        )
        print(f"config_hash={fingerprint}")
        print(f"checkpoint={checkpoint.with_suffix('.zip')}")
        print(f"training log={output_dir / 'training.monitor.csv'}")
        print(f"training proof={proof_dir / 'tray_ppo_training.json'}")
        print("Run simulation.eval to measure success; training completion is not task success.")
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--timesteps", type=int)
    parser.add_argument("--n-steps", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--gamma", type=float)
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--device", choices=("cpu", "cuda", "auto"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--proof-dir", type=Path, default=DEFAULT_PROOF_DIR)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    try:
        defaults = json.loads(args.config.read_text(encoding="utf-8"))
        run_training(
            seed=args.seed if args.seed is not None else defaults["seed"],
            timesteps=(
                args.timesteps
                if args.timesteps is not None
                else defaults["total_timesteps"]
            ),
            n_steps=args.n_steps if args.n_steps is not None else defaults["n_steps"],
            batch_size=(
                args.batch_size
                if args.batch_size is not None
                else defaults["batch_size"]
            ),
            gamma=args.gamma if args.gamma is not None else defaults["gamma"],
            max_steps=(
                args.max_steps
                if args.max_steps is not None
                else defaults["max_episode_steps"]
            ),
            device=(
                args.device if args.device is not None else defaults.get("device", "cpu")
            ),
            output_dir=args.output_dir,
            proof_dir=args.proof_dir,
            quiet=args.quiet,
        )
    except (ImportError, OSError, KeyError, json.JSONDecodeError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
