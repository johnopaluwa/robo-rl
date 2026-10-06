# simulation/

MuJoCo / Isaac Sim environments, reward functions, and RL training scripts
live here (Phase 2 of the roadmap).

Suggested structure as this grows:
```
simulation/
├── envs/            # custom gymnasium-style environments for your task
├── train/           # training scripts (Stable-Baselines3 configs, etc.)
├── policies/        # saved checkpoints
└── videos/          # recorded eval rollouts (the proof you show people)
```
Nothing here yet — start with `pip install gymnasium stable-baselines3 mujoco`
and a stock environment before writing your own.
