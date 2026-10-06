"""Train and evaluate a Stable-Baselines3 PPO sanity-check on Pendulum-v1.

From the repository root, after installing the optional PPO requirements::

    python3 -m simulation.train.train_stock_ppo
    python3 -m simulation.train.train_stock_ppo --seed 12 --timesteps 100000

The default configuration is ``stock_ppo_config.json``. Checkpoints, Monitor
logs and machine-readable proofs go under ignored ``artifacts/`` by default.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from simulation.proof_utils import (
    config_hash,
    file_sha256,
    git_commit,
    git_worktree_dirty,
    source_hash,
    write_json,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = Path(__file__).with_name("stock_ppo_config.json")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "simulation" / "stock_ppo"
DEFAULT_PROOF_DIR = REPO_ROOT / "artifacts" / "proofs"


def run_training(
    *,
    seed: int,
    timesteps: int,
    eval_episodes: int,
    n_steps: int,
    batch_size: int,
    gamma: float,
    environment: str,
    device: str,
    output_dir: Path,
    proof_dir: Path,
    quiet: bool = False,
) -> dict:
    if timesteps <= 0 or eval_episodes <= 0 or n_steps <= 1 or batch_size <= 0:
        raise ValueError("timesteps/eval_episodes/batch_size must be positive and n_steps > 1")
    if batch_size > n_steps or n_steps % batch_size != 0:
        raise ValueError("batch_size must divide n_steps evenly")
    if not 0.0 < gamma <= 1.0:
        raise ValueError("gamma must be in (0, 1]")

    try:
        import gymnasium as gym
        import stable_baselines3
        import torch
        from stable_baselines3 import PPO
        from stable_baselines3.common.evaluation import evaluate_policy
        from stable_baselines3.common.monitor import Monitor
    except ImportError as error:
        raise RuntimeError(
            "PPO training dependencies are missing; install "
            "simulation/requirements-rl.txt"
        ) from error

    output_dir.mkdir(parents=True, exist_ok=True)
    training_env = Monitor(
        gym.make(environment), filename=str(output_dir / "training")
    )
    evaluation_env = gym.make(environment)
    training_env.reset(seed=seed)
    evaluation_env.reset(seed=seed + 100_000)

    config = {
        "algorithm": "PPO",
        "environment": environment,
        "policy": "MlpPolicy",
        "seed": seed,
        "requested_timesteps": timesteps,
        "eval_episodes": eval_episodes,
        "n_steps": n_steps,
        "batch_size": batch_size,
        "gamma": gamma,
        "device": device,
        "deterministic_evaluation": True,
        "gymnasium_version": gym.__version__,
        "stable_baselines3_version": stable_baselines3.__version__,
        "torch_version": torch.__version__,
        "trainer_source_hash": source_hash(
            Path(__file__).resolve(), Path(__file__).resolve().parents[1] / "proof_utils.py"
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
        rewards, lengths = evaluate_policy(
            model,
            evaluation_env,
            n_eval_episodes=eval_episodes,
            deterministic=True,
            return_episode_rewards=True,
            warn=False,
        )
    finally:
        training_env.close()
        evaluation_env.close()

    metrics = {
        "proof": "stock-gymnasium-ppo-baseline",
        "verdict": "PASS",
        "transport": "Gymnasium environment (not MuJoCo hardware or ROS 2)",
        "seed": seed,
        "config_hash": fingerprint,
        "episodes": eval_episodes,
        "success_rate": None,
        "mean_reward": float(statistics.mean(rewards)),
        "std_reward": float(statistics.pstdev(rewards)),
        "mean_episode_length": float(statistics.mean(lengths)),
        "requested_timesteps": timesteps,
        "actual_timesteps": actual_timesteps,
        "checkpoint": str(checkpoint.with_suffix(".zip")),
        "checkpoint_sha256": file_sha256(checkpoint.with_suffix(".zip")),
        "training_log": str(output_dir / "training.monitor.csv"),
        "git_commit": git_commit(),
        "git_worktree_dirty": git_worktree_dirty(),
        "proves": [
            "Stable-Baselines3 PPO can train and evaluate on the stock Gymnasium task",
            "the training seed, config, dependency versions, and Monitor log are recorded",
        ],
        "does_not_prove": [
            "the custom bakery task is solved",
            "a MuJoCo policy has >80% randomized-condition success",
            "physical robot or ROS 2 performance",
        ],
    }
    write_json(output_dir / "config.json", config)
    write_json(output_dir / "metrics.json", metrics)
    write_json(proof_dir / "stock_ppo.json", metrics)
    if not quiet:
        print(
            f"PPO {environment}: {actual_timesteps} timesteps, "
            f"mean evaluation reward {metrics['mean_reward']:.3f} "
            f"± {metrics['std_reward']:.3f} (n={eval_episodes}, seed={seed})"
        )
        print(f"config_hash={fingerprint}")
        print(f"checkpoint={checkpoint.with_suffix('.zip')}")
        print(f"training log={output_dir / 'training.monitor.csv'}")
        print(f"proof={proof_dir / 'stock_ppo.json'}")
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--timesteps", type=int)
    parser.add_argument("--eval-episodes", type=int)
    parser.add_argument("--n-steps", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--gamma", type=float)
    parser.add_argument("--environment")
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
            eval_episodes=(
                args.eval_episodes
                if args.eval_episodes is not None
                else defaults["eval_episodes"]
            ),
            n_steps=args.n_steps if args.n_steps is not None else defaults["n_steps"],
            batch_size=(
                args.batch_size
                if args.batch_size is not None
                else defaults["batch_size"]
            ),
            gamma=args.gamma if args.gamma is not None else defaults["gamma"],
            environment=(
                args.environment
                if args.environment is not None
                else defaults["environment"]
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
