"""Seeded evaluation of a PPO checkpoint on randomized bakery-tray episodes.

Example::

    python3 -m simulation.eval \\
      --model artifacts/simulation/tray_ppo/model.zip --seed 70 --episodes 100

Use ``--min-success-rate 0.80`` to make the command fail unless the seeded
success rate reaches the Phase 2 target. Evaluation proofs record the seed,
checkpoint hash and environment config; they never imply hardware performance.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from simulation.envs.tray_loading import TrayLoadingEnv
from simulation.proof_utils import (
    config_hash,
    file_sha256,
    git_commit,
    git_worktree_dirty,
    source_hash,
    write_json,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROOF_DIR = REPO_ROOT / "artifacts" / "proofs"


def evaluate(
    *,
    model_path: Path,
    seed: int,
    episodes: int,
    deterministic: bool,
    max_steps: int,
    proof_dir: Path,
    min_success_rate: float | None = None,
    quiet: bool = False,
) -> dict:
    if not model_path.is_file():
        raise ValueError(f"model checkpoint does not exist: {model_path}")
    if episodes <= 0 or max_steps <= 0:
        raise ValueError("episodes and max_steps must be positive")
    if min_success_rate is not None and not 0.0 <= min_success_rate <= 1.0:
        raise ValueError("min_success_rate must be between 0 and 1")
    try:
        from stable_baselines3 import PPO
    except ImportError as error:
        raise RuntimeError(
            "PPO evaluation dependencies are missing; install "
            "simulation/requirements-rl.txt"
        ) from error

    checkpoint_hash = file_sha256(model_path)
    env_source = Path(__file__).parent / "envs" / "tray_loading.py"
    model_source = env_source.parent / "assets" / "tray_loading.xml"
    randomization_source = Path(__file__).parent / "domain_randomization.py"
    sources_hash = source_hash(
        Path(__file__).resolve(),
        env_source,
        model_source,
        randomization_source,
        Path(__file__).parent / "proof_utils.py",
    )
    config = {
        "environment": "simulation.envs.tray_loading.TrayLoadingEnv",
        "seed": seed,
        "episodes": episodes,
        "max_steps": max_steps,
        "deterministic": deterministic,
        "min_success_rate": min_success_rate,
        "checkpoint_sha256": checkpoint_hash,
        "environment_source_hash": sources_hash,
    }
    fingerprint = config_hash(config)
    model = PPO.load(str(model_path), device="cpu")
    env = TrayLoadingEnv(max_steps=max_steps)
    episode_results = []
    try:
        for episode in range(episodes):
            episode_seed = seed + episode
            observation, reset_info = env.reset(seed=episode_seed)
            total_reward = 0.0
            length = 0
            final_info = reset_info
            terminated = truncated = False
            while not (terminated or truncated):
                action, _ = model.predict(observation, deterministic=deterministic)
                observation, reward, terminated, truncated, final_info = env.step(action)
                total_reward += float(reward)
                length += 1
            episode_results.append(
                {
                    "episode": episode,
                    "seed": episode_seed,
                    "success": bool(final_info.get("is_success", False)),
                    "dropped": bool(final_info.get("dropped", False)),
                    "length": length,
                    "return": total_reward,
                    "domain_parameters": final_info.get("domain_parameters"),
                }
            )
    finally:
        env.close()

    successes = sum(int(result["success"]) for result in episode_results)
    success_rate = successes / episodes
    task_target_met = (
        None if min_success_rate is None else success_rate >= min_success_rate
    )
    verdict = (
        "COMPLETE"
        if task_target_met is None
        else "PASS" if task_target_met else "FAIL"
    )
    proof = {
        "proof": "randomized-tray-loading-policy-evaluation",
        "verdict": verdict,
        "evaluation_completed": True,
        "transport": "MuJoCo + Gymnasium (simulation only)",
        "seed": seed,
        "config_hash": fingerprint,
        "checkpoint_sha256": checkpoint_hash,
        "episodes": episodes,
        "successes": successes,
        "success_rate": success_rate,
        "mean_episode_length": float(np.mean([item["length"] for item in episode_results])),
        "mean_return": float(np.mean([item["return"] for item in episode_results])),
        "deterministic_policy": deterministic,
        "min_success_rate": min_success_rate,
        "task_target_met": task_target_met,
        "environment_source_hash": sources_hash,
        "git_commit": git_commit(),
        "git_worktree_dirty": git_worktree_dirty(),
        "episode_results": episode_results,
        "proves": [
            "this exact checkpoint was evaluated on the recorded seeds and domain parameters",
            "the observed randomized-simulation success rate is reproducible from the command/config",
        ],
        "does_not_prove": [
            "success under domain shifts outside the configured randomization ranges",
            "physical gripper contact, perception or sim-to-real transfer",
            "any ROS 2 or physical-hardware milestone",
        ],
    }
    write_json(proof_dir / "tray_loading_eval.json", proof)
    if not quiet:
        print(
            f"Tray-loading PPO: {successes}/{episodes} successful "
            f"({success_rate:.1%}), seed={seed}, deterministic={deterministic}"
        )
        print(f"config_hash={fingerprint} checkpoint_sha256={checkpoint_hash}")
        print(f"proof={proof_dir / 'tray_loading_eval.json'}")
        if task_target_met is False:
            print(f"FAIL: target was at least {min_success_rate:.1%}")
        elif task_target_met is None:
            print("No success threshold supplied; evaluation completed without claiming a target pass.")
    return proof


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=70)
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--max-steps", type=int, default=180)
    parser.add_argument("--stochastic", action="store_true")
    parser.add_argument("--min-success-rate", type=float)
    parser.add_argument("--proof-dir", type=Path, default=DEFAULT_PROOF_DIR)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    try:
        proof = evaluate(
            model_path=args.model,
            seed=args.seed,
            episodes=args.episodes,
            deterministic=not args.stochastic,
            max_steps=args.max_steps,
            proof_dir=args.proof_dir,
            min_success_rate=args.min_success_rate,
            quiet=args.quiet,
        )
    except (ImportError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    return 1 if proof["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
