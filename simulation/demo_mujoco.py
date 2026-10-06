"""Run a deterministic scripted tray transfer in the MuJoCo scene.

Examples (from the repository root)::

    python3 -m simulation.demo_mujoco --episodes 3 --seed 7
    python3 -m simulation.demo_mujoco --seed 7 --video artifacts/tray-demo.mp4

The scripted controller is a simulator smoke test, not an RL policy and not
proof of physical-robot performance. The JSON proof is written under the
ignored ``artifacts/`` directory by default.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np

from simulation.envs.tray_loading import (
    ACTION_STEP_METRES,
    TRAY_REST_Z,
    TrayLoadingEnv,
)
from simulation.proof_utils import (
    config_hash,
    git_commit,
    git_worktree_dirty,
    source_hash,
    write_json,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = REPO_ROOT / "artifacts" / "proofs"


def _run_config(seed: int, episodes: int) -> dict[str, Any]:
    env_source = Path(__file__).parent / "envs" / "tray_loading.py"
    model_source = env_source.parent / "assets" / "tray_loading.xml"
    randomization_source = Path(__file__).parent / "domain_randomization.py"
    render_source = Path(__file__).parent / "rendering.py"
    return {
        "seed": seed,
        "episodes": episodes,
        "controller": "scripted-cartesian-v1",
        "source_hash": source_hash(
            Path(__file__).resolve(),
            env_source,
            model_source,
            randomization_source,
            render_source,
            Path(__file__).parent / "proof_utils.py",
        ),
    }


def _drive_to(
    env: TrayLoadingEnv,
    destination: np.ndarray,
    *,
    close_gripper: bool,
    frame_sink: list[np.ndarray] | None,
    max_steps: int = 100,
) -> dict[str, Any]:
    last_info: dict[str, Any] = {}
    for _ in range(max_steps):
        delta = np.asarray(destination, dtype=np.float64) - env.tool_position
        needs_motion = float(np.max(np.abs(delta))) > 0.012
        needs_gripper_change = env.gripper_closed != close_gripper
        if not needs_motion and not needs_gripper_change:
            return last_info

        action = np.zeros(4, dtype=np.float32)
        action[:3] = np.clip(delta / ACTION_STEP_METRES, -1.0, 1.0)
        action[3] = 1.0 if close_gripper else -1.0
        _, reward, terminated, truncated, last_info = env.step(action)
        last_info = {**last_info, "last_reward": float(reward)}
        if frame_sink is not None:
            frame = env.render()
            if frame is not None:
                frame_sink.append(frame)
        if terminated or truncated:
            return last_info
    raise RuntimeError(f"scripted controller could not reach {destination.tolist()}")


def run_scripted_episode(
    env: TrayLoadingEnv,
    *,
    seed: int,
    frame_sink: list[np.ndarray] | None = None,
) -> dict[str, Any]:
    """Run a simple open-loop stage plan with feedback on tool position."""
    env.reset(seed=seed)
    if frame_sink is not None:
        frame = env.render()
        if frame is not None:
            frame_sink.append(frame)

    source = env.tray_position
    target = env.target_position
    hover_height = TRAY_REST_Z + 0.20
    _drive_to(
        env,
        np.asarray([source[0], source[1], hover_height]),
        close_gripper=False,
        frame_sink=frame_sink,
    )
    _drive_to(
        env,
        np.asarray([source[0], source[1], source[2]]),
        close_gripper=False,
        frame_sink=frame_sink,
    )
    grasp_info = _drive_to(
        env,
        np.asarray([source[0], source[1], source[2]]),
        close_gripper=True,
        frame_sink=frame_sink,
    )
    if not grasp_info.get("is_attached", False):
        raise RuntimeError("scripted controller reached the tray but did not grasp it")

    _drive_to(
        env,
        np.asarray([source[0], source[1], hover_height]),
        close_gripper=True,
        frame_sink=frame_sink,
    )
    _drive_to(
        env,
        np.asarray([target[0], target[1], hover_height]),
        close_gripper=True,
        frame_sink=frame_sink,
    )
    _drive_to(
        env,
        np.asarray([target[0], target[1], target[2]]),
        close_gripper=True,
        frame_sink=frame_sink,
    )
    final_info = _drive_to(
        env,
        np.asarray([target[0], target[1], target[2]]),
        close_gripper=False,
        frame_sink=frame_sink,
    )
    if not final_info.get("is_success", False):
        raise RuntimeError(
            "scripted transfer did not complete successfully; "
            f"last environment state: {final_info}"
        )
    return final_info


def _write_video(path: Path, frames: list[np.ndarray]) -> None:
    try:
        import imageio.v3 as iio
    except ImportError as error:
        raise RuntimeError(
            "video export needs the optional dependency; install "
            "simulation/requirements-video.txt"
        ) from error
    if not frames:
        raise RuntimeError("no rendered frames were produced")
    path.parent.mkdir(parents=True, exist_ok=True)
    video_frames = np.stack(frames)
    if path.suffix.lower() == ".gif":
        iio.imwrite(path, video_frames, fps=30)
    else:
        # 800x500 is valid for 4:2:0 video (both dimensions are even); avoid
        # ImageIO's default 16-pixel padding so the diagnostic frame is unscaled.
        iio.imwrite(path, video_frames, fps=30, macro_block_size=2)


def run_demo(
    *,
    seed: int = 7,
    episodes: int = 3,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    video_path: Path | None = None,
    quiet: bool = False,
) -> dict[str, Any]:
    if episodes <= 0:
        raise ValueError("episodes must be a positive integer")
    all_frames: list[np.ndarray] | None = [] if video_path is not None else None
    successes = 0
    episode_results = []
    env = TrayLoadingEnv(render_mode="rgb_array" if video_path is not None else None)
    try:
        for episode in range(episodes):
            frame_sink = all_frames if episode == 0 else None
            result = run_scripted_episode(env, seed=seed + episode, frame_sink=frame_sink)
            successes += int(result["is_success"])
            episode_results.append(
                {
                    "episode": episode,
                    "seed": seed + episode,
                    "success": bool(result["is_success"]),
                    "domain_parameters": result["domain_parameters"],
                }
            )
    finally:
        env.close()

    success_rate = successes / episodes
    if video_path is not None and all_frames is not None:
        _write_video(video_path, all_frames)

    run_config = _run_config(seed, episodes)
    proof = {
        "proof": "mujoco-tray-loading-demo",
        "verdict": "PASS" if successes == episodes else "FAIL",
        "transport": "MuJoCo tray physics + scripted virtual-grasp controller (simulation only)",
        "seed": seed,
        "config": run_config,
        "config_hash": config_hash(run_config),
        "episodes": episodes,
        "successes": successes,
        "success_rate": success_rate,
        "git_commit": git_commit(),
        "git_worktree_dirty": git_worktree_dirty(),
        "video": str(video_path) if video_path is not None else None,
        "video_metadata": (
            {
                "episode_seed": seed,
                "frames": len(all_frames) if all_frames is not None else 0,
                "width": 800,
                "height": 500,
                "renderer": "headless software diagnostic projection",
            }
            if video_path is not None
            else None
        ),
        "episode_results": episode_results,
        "proves": [
            "the MuJoCo model loads and advances headlessly",
            "tray pickup, transfer and release work with the scripted smoke-test controller",
            "episode domain parameters are emitted for reproducibility",
        ],
        "does_not_prove": [
            "that a PPO or other learned policy can solve the task",
            "physical gripper contact, camera perception, or sim-to-real transfer",
            "any ROS 2 or physical-hardware milestone",
        ],
    }
    proof_path = artifact_dir / "mujoco_demo.json"
    write_json(proof_path, proof)

    if not quiet:
        print(
            f"MuJoCo scripted demo: {proof['verdict']} — "
            f"{successes}/{episodes} transfers ({success_rate:.0%})"
        )
        print(f"seed={seed} config_hash={proof['config_hash']}")
        print(f"proof={proof_path.relative_to(REPO_ROOT) if proof_path.is_relative_to(REPO_ROOT) else proof_path}")
        if video_path is not None:
            print(f"video={video_path}")
        print("This is a simulator smoke test, not a learned-policy or hardware result.")
    return proof


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--video", type=Path, help="optional MP4/GIF recording (needs imageio[ffmpeg])")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    try:
        proof = run_demo(
            seed=args.seed,
            episodes=args.episodes,
            artifact_dir=args.artifact_dir,
            video_path=args.video,
            quiet=args.quiet,
        )
    except (ImportError, RuntimeError, ValueError) as error:
        print(f"MuJoCo demo failed: {error}", file=sys.stderr)
        return 1
    return 0 if proof["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
