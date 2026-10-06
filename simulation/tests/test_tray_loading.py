"""MuJoCo integration tests for the randomized bakery-tray environment."""

import unittest

import numpy as np

from simulation.demo_mujoco import run_scripted_episode
from simulation.envs.tray_loading import (
    ACTION_STEP_METRES,
    TRAY_REST_Z,
    TrayLoadingEnv,
)


class TrayLoadingEnvironmentTests(unittest.TestCase):
    def test_rgb_diagnostic_renderer_works_without_a_gl_context(self):
        env = TrayLoadingEnv(render_mode="rgb_array")
        try:
            env.reset(seed=11)
            frame = env.render()
            self.assertEqual(frame.shape, (500, 800, 3))
            self.assertEqual(frame.dtype, np.uint8)
        finally:
            env.close()

    def test_gymnasium_environment_checker_accepts_the_env(self):
        from gymnasium.utils.env_checker import check_env

        env = TrayLoadingEnv()
        try:
            check_env(env, skip_render_check=True)
        finally:
            env.close()

    def test_reset_and_step_follow_the_gymnasium_contract(self):
        env = TrayLoadingEnv(max_steps=3)
        try:
            observation, info = env.reset(seed=12)
            self.assertTrue(env.observation_space.contains(observation))
            self.assertIn("domain_parameters", info)
            self.assertEqual(observation.shape, (11,))
            self.assertEqual(observation.dtype, np.float32)

            for step in range(3):
                observation, reward, terminated, truncated, info = env.step(
                    np.zeros(4, dtype=np.float32)
                )
                self.assertTrue(env.observation_space.contains(observation))
                self.assertTrue(np.isfinite(reward))
                self.assertFalse(terminated)
                self.assertEqual(truncated, step == 2)
            with self.assertRaises(RuntimeError):
                env.step(np.zeros(4, dtype=np.float32))
        finally:
            env.close()

    def test_seed_reproduces_observation_and_all_randomized_parameters(self):
        env = TrayLoadingEnv()
        try:
            first_observation, first_info = env.reset(seed=40)
            first_tray_size = env.model.geom_size[env._tray_geom_id].copy()
            second_observation, second_info = env.reset(seed=40)
            second_tray_size = env.model.geom_size[env._tray_geom_id].copy()
            np.testing.assert_array_equal(first_observation, second_observation)
            self.assertEqual(first_info["domain_parameters"], second_info["domain_parameters"])
            np.testing.assert_array_equal(first_tray_size, second_tray_size)
        finally:
            env.close()

    def test_randomization_changes_scene_position_size_friction_and_lighting(self):
        env = TrayLoadingEnv()
        try:
            snapshots = []
            for seed in range(8):
                _, info = env.reset(seed=seed)
                params = info["domain_parameters"]
                snapshots.append(
                    (
                        params["source_x"],
                        params["target_y"],
                        params["tray_scale"],
                        params["friction"],
                        params["light_intensity"],
                    )
                )
                np.testing.assert_allclose(
                    env.model.geom_size[env._tray_geom_id, :2],
                    np.asarray([0.10, 0.07]) * params["tray_scale"],
                )
                self.assertAlmostEqual(
                    env.model.geom_friction[env._tray_geom_id, 0],
                    params["friction"],
                    delta=1e-6,
                )
                self.assertAlmostEqual(
                    env.model.light_diffuse[env._light_id, 0],
                    params["light_intensity"],
                    delta=1e-6,
                )
                np.testing.assert_allclose(
                    env.tray_position[:2], np.asarray([params["source_x"], params["source_y"]]),
                    atol=0.01,
                )
                np.testing.assert_allclose(
                    env.target_position[:2], np.asarray([params["target_x"], params["target_y"]]),
                )
            for column in range(5):
                self.assertGreater(len({snapshot[column] for snapshot in snapshots}), 1)
        finally:
            env.close()

    def test_scripted_controller_can_pick_transfer_and_release_randomized_trays(self):
        env = TrayLoadingEnv()
        try:
            for seed in (3, 17, 101):
                with self.subTest(seed=seed):
                    result = run_scripted_episode(env, seed=seed)
                    self.assertTrue(result["is_success"])
                    self.assertFalse(result["dropped"])
                    self.assertGreater(result["last_reward"], 0.0)
                    self.assertLessEqual(
                        result["distance_to_target"], 0.16
                    )
        finally:
            env.close()

    def test_release_outside_target_is_a_terminal_drop(self):
        env = TrayLoadingEnv()
        try:
            env.reset(seed=5)
            source = env.tray_position
            self._drive_to(env, source, close=False)
            grasp = self._drive_to(env, source, close=True)
            self.assertTrue(grasp["is_attached"])
            drop = self._drive_to(env, source, close=False)
            self.assertTrue(drop["dropped"])
            self.assertFalse(drop["is_success"])
            self.assertLess(drop["last_reward"], 0.0)
        finally:
            env.close()

    @staticmethod
    def _drive_to(env, position, *, close):
        last_info = {}
        for _ in range(80):
            delta = np.asarray(position) - env.tool_position
            needs_motion = np.max(np.abs(delta)) > 0.012
            if not needs_motion and env.gripper_closed == close:
                return last_info
            action = np.zeros(4, dtype=np.float32)
            action[:3] = np.clip(delta / ACTION_STEP_METRES, -1.0, 1.0)
            action[3] = 1.0 if close else -1.0
            _, reward, terminated, truncated, last_info = env.step(action)
            last_info = {**last_info, "last_reward": float(reward)}
            if terminated or truncated:
                return last_info
        self.fail(f"test controller failed to reach {position.tolist()} at z={TRAY_REST_Z}")


if __name__ == "__main__":
    unittest.main()
