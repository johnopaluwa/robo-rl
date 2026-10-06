# Checked-in Phase 2 baseline result

This small run record is checked in because the Phase 2 stock-PPO milestone
calls for a reproducible configuration, training log and evaluation number.
It is not a claim about the custom task.

- Configuration: `stock_ppo_seed7_config.json`
- Training episodes: `stock_ppo_seed7_training.monitor.csv`
- Evaluation/proof: `stock_ppo_seed7_eval.json`
- Re-run: `python3 -m simulation.train.train_stock_ppo --config simulation/train/stock_ppo_config.json`
- Task: Gymnasium `Pendulum-v1`, PPO MLP, seed 7, requested 50,000 steps, 10 deterministic evaluation episodes.
- Result: 50,176 actual steps; mean evaluation return -1,030.014 (standard deviation 293.969).

The checkpoint itself stays out of Git under ignored `artifacts/`; its SHA-256 is
in the proof record. The run records that the worktree was dirty and includes a
source hash rather than pretending it ran from a clean commit. PPO's final
rollout advances in full `n_steps=1024` batches, explaining 50,176 actual steps.

`tray_ppo_debug_seed7.json` records a separate 1,024-step custom-task smoke run
that achieved 0/3 at an intentionally shortened 40-step episode limit. It only
proves the train/evaluate path executes; it is not a policy-performance result.
