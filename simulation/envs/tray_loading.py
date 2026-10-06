"""MuJoCo/Gymnasium prototype of bakery baking-tray loading.

The scene is deliberately a small, controllable first simulation rather than a
claim of robot-arm fidelity. MuJoCo simulates the free tray, gravity and table
contacts. The Cartesian tool is a position-controlled arm abstraction, and a
successful close creates a virtual grasp constraint. That keeps the task
focused on the tray transfer and domain-randomization loop; it does *not* model
gripper contact, arm kinematics, perception, an oven, or sim-to-real transfer.

Install ``simulation/requirements-sim.txt`` to use this environment.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import gymnasium as gym
import mujoco
import numpy as np
from gymnasium import spaces

from simulation.domain_randomization import DomainParameters, sample_domain_parameters


ASSET_PATH = Path(__file__).parent / "assets" / "tray_loading.xml"
TABLE_SURFACE_Z = 0.60
TRAY_HALF_THICKNESS = 0.012
TRAY_REST_Z = TABLE_SURFACE_Z + TRAY_HALF_THICKNESS
ACTION_STEP_METRES = 0.025
DEFAULT_SUBSTEPS = 5
DEFAULT_MAX_STEPS = 180
TARGET_RADIUS_METRES = 0.155
GRASP_RADIUS_METRES = 0.105


class TrayLoadingEnv(gym.Env[np.ndarray, np.ndarray]):
    """Move one randomized baking tray from the pickup area to a target zone.

    Actions are ``[dx, dy, dz, gripper]`` in ``[-1, 1]``. The first three
    values move the Cartesian tool by at most 2.5 cm per decision. A positive
    final value closes the virtual gripper; a non-positive value opens it.

    Observations contain the tool, tray and target positions in metres, then
    ``[gripper_closed, tray_attached]``. A successful release terminates the
    episode; a release outside the target counts as a dropped tray.
    """

    metadata = {"render_modes": ["rgb_array"], "render_fps": 20}

    def __init__(
        self,
        *,
        render_mode: str | None = None,
        randomize: bool = True,
        max_steps: int = DEFAULT_MAX_STEPS,
        frame_skip: int = DEFAULT_SUBSTEPS,
    ) -> None:
        if render_mode not in (None, "rgb_array"):
            raise ValueError("render_mode must be None or 'rgb_array'")
        if max_steps <= 0:
            raise ValueError("max_steps must be a positive integer")
        if frame_skip <= 0:
            raise ValueError("frame_skip must be a positive integer")

        self.render_mode = render_mode
        self.randomize = randomize
        self.max_steps = int(max_steps)
        self.frame_skip = int(frame_skip)
        self.model = mujoco.MjModel.from_xml_path(str(ASSET_PATH))
        self.data = mujoco.MjData(self.model)

        self._tool_body_id = self._id(mujoco.mjtObj.mjOBJ_BODY, "gripper_tool")
        self._tray_body_id = self._id(mujoco.mjtObj.mjOBJ_BODY, "baking_tray")
        self._tray_geom_id = self._id(mujoco.mjtObj.mjOBJ_GEOM, "tray_geom")
        self._target_geom_id = self._id(mujoco.mjtObj.mjOBJ_GEOM, "target_marker")
        self._light_id = self._id(mujoco.mjtObj.mjOBJ_LIGHT, "key_light")
        tray_joint_id = self._id(mujoco.mjtObj.mjOBJ_JOINT, "tray_free")
        self._tray_qpos_adr = int(self.model.jnt_qposadr[tray_joint_id])
        self._tray_dof_adr = int(self.model.jnt_dofadr[tray_joint_id])
        self._slide_qpos_adrs = np.asarray(
            [
                self.model.jnt_qposadr[self._id(mujoco.mjtObj.mjOBJ_JOINT, name)]
                for name in ("eef_x", "eef_y", "eef_z")
            ],
            dtype=np.int32,
        )
        self._actuator_ids = np.asarray(
            [
                self._id(mujoco.mjtObj.mjOBJ_ACTUATOR, name)
                for name in ("move_x", "move_y", "move_z")
            ],
            dtype=np.int32,
        )
        self._slide_ranges = self.model.jnt_range[
            [self._id(mujoco.mjtObj.mjOBJ_JOINT, name) for name in ("eef_x", "eef_y", "eef_z")]
        ].copy()
        self._base_tray_size = self.model.geom_size[self._tray_geom_id].copy()
        self._base_light_diffuse = self.model.light_diffuse[self._light_id].copy()

        self.action_space = spaces.Box(
            low=np.full(4, -1.0, dtype=np.float32),
            high=np.full(4, 1.0, dtype=np.float32),
            dtype=np.float32,
        )
        observation_low = np.asarray([-1.0] * 9 + [0.0, 0.0], dtype=np.float32)
        observation_high = np.asarray([1.0] * 9 + [1.0, 1.0], dtype=np.float32)
        self.observation_space = spaces.Box(
            low=observation_low, high=observation_high, dtype=np.float32
        )

        self.domain_parameters = DomainParameters(
            source_x=-0.29,
            source_y=0.0,
            target_x=0.29,
            target_y=0.0,
            tray_scale=1.0,
            friction=0.9,
            light_intensity=0.8,
        )
        self._gripper_closed = False
        self._attached = False
        self._grasp_offset = np.zeros(3, dtype=np.float64)
        self._elapsed_steps = 0
        self._success = False
        self._dropped = False
        self._episode_done = False

    def _id(self, object_type: mujoco.mjtObj, name: str) -> int:
        object_id = mujoco.mj_name2id(self.model, object_type, name)
        if object_id < 0:
            raise RuntimeError(f"MuJoCo model is missing {object_type.name} '{name}'")
        return int(object_id)

    @property
    def tool_position(self) -> np.ndarray:
        """Current world-space Cartesian tool position, in metres."""
        return self.data.xpos[self._tool_body_id].copy()

    @property
    def tray_position(self) -> np.ndarray:
        """Current tray centre in world coordinates, in metres."""
        return self.data.xpos[self._tray_body_id].copy()

    @property
    def target_position(self) -> np.ndarray:
        """Target tray-centre position for the current episode."""
        return np.asarray(
            [
                self.domain_parameters.target_x,
                self.domain_parameters.target_y,
                TRAY_REST_Z,
            ],
            dtype=np.float64,
        )

    @property
    def gripper_closed(self) -> bool:
        return self._gripper_closed

    @property
    def tray_attached(self) -> bool:
        return self._attached

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        options = options or {}
        if self.randomize:
            params = sample_domain_parameters(self.np_random)
        else:
            params = DomainParameters(
                source_x=-0.29,
                source_y=0.0,
                target_x=0.29,
                target_y=0.0,
                tray_scale=1.0,
                friction=0.9,
                light_intensity=0.8,
            )
        override = options.get("domain_parameters")
        if override is not None:
            if isinstance(override, DomainParameters):
                params = override
            elif isinstance(override, dict):
                params = DomainParameters(**override)
            else:
                raise TypeError("options['domain_parameters'] must be a dict or DomainParameters")
        self.domain_parameters = params
        self._apply_domain_parameters(params)

        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[self._slide_qpos_adrs] = np.asarray([0.0, 0.0, 0.30])
        self.data.ctrl[self._actuator_ids] = self.data.qpos[self._slide_qpos_adrs]
        self.data.qpos[self._tray_qpos_adr : self._tray_qpos_adr + 3] = np.asarray(
            [params.source_x, params.source_y, TRAY_REST_Z]
        )
        # A MuJoCo free joint stores quaternion as w, x, y, z.
        self.data.qpos[self._tray_qpos_adr + 3 : self._tray_qpos_adr + 7] = np.asarray(
            [1.0, 0.0, 0.0, 0.0]
        )
        mujoco.mj_forward(self.model, self.data)

        self._gripper_closed = False
        self._attached = False
        self._grasp_offset.fill(0.0)
        self._elapsed_steps = 0
        self._success = False
        self._dropped = False
        self._episode_done = False
        observation = self._observation()
        return observation, {"domain_parameters": params.to_dict()}

    def _apply_domain_parameters(self, params: DomainParameters) -> None:
        numeric_values = params.to_dict().values()
        if not all(
            isinstance(value, (int, float, np.number))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            for value in numeric_values
        ):
            raise ValueError("domain parameters must all be finite numbers")
        if not -0.45 <= params.source_x <= -0.10:
            raise ValueError("source_x must be between -0.45 and -0.10 metres")
        if not -0.25 <= params.source_y <= 0.25:
            raise ValueError("source_y must be between -0.25 and 0.25 metres")
        if not 0.10 <= params.target_x <= 0.45:
            raise ValueError("target_x must be between 0.10 and 0.45 metres")
        if not -0.25 <= params.target_y <= 0.25:
            raise ValueError("target_y must be between -0.25 and 0.25 metres")
        if not 0.6 <= params.tray_scale <= 1.4:
            raise ValueError("tray_scale must be between 0.6 and 1.4")
        if not 0.1 <= params.friction <= 3.0:
            raise ValueError("friction must be between 0.1 and 3.0")
        if not 0.0 <= params.light_intensity <= 2.0:
            raise ValueError("light_intensity must be between 0 and 2")

        self.model.geom_size[self._tray_geom_id] = self._base_tray_size * np.asarray(
            [params.tray_scale, params.tray_scale, 1.0]
        )
        self.model.geom_friction[self._tray_geom_id, 0] = params.friction
        self.model.light_diffuse[self._light_id] = (
            self._base_light_diffuse * params.light_intensity / 0.8
        )
        self.model.geom_pos[self._target_geom_id] = np.asarray(
            [params.target_x, params.target_y, TABLE_SURFACE_Z + 0.003]
        )

    def _observation(self) -> np.ndarray:
        return np.asarray(
            [
                *self.tool_position,
                *self.tray_position,
                *self.target_position,
                float(self._gripper_closed),
                float(self._attached),
            ],
            dtype=np.float32,
        )

    def _try_grasp(self) -> bool:
        tool = self.tool_position
        tray = self.tray_position
        horizontal_distance = float(np.linalg.norm(tool[:2] - tray[:2]))
        vertical_distance = abs(float(tool[2] - tray[2]))
        if (
            horizontal_distance <= GRASP_RADIUS_METRES * self.domain_parameters.tray_scale
            and vertical_distance <= 0.075
        ):
            self._attached = True
            self._grasp_offset = tray - tool
            self.data.qvel[
                self._tray_dof_adr : self._tray_dof_adr + 6
            ] = 0.0
            return True
        return False

    def _follow_tool(self) -> None:
        if not self._attached:
            return
        tray_xyz = self.tool_position + self._grasp_offset
        self.data.qpos[self._tray_qpos_adr : self._tray_qpos_adr + 3] = tray_xyz
        self.data.qvel[self._tray_dof_adr : self._tray_dof_adr + 6] = 0.0
        mujoco.mj_forward(self.model, self.data)

    def _release_is_successful(self) -> bool:
        tray = self.tray_position
        xy_error = float(np.linalg.norm(tray[:2] - self.target_position[:2]))
        z_error = abs(float(tray[2] - TRAY_REST_Z))
        return xy_error <= TARGET_RADIUS_METRES and z_error <= 0.075

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        if self._episode_done:
            raise RuntimeError("step() called after the episode ended; call reset() first")
        action = np.asarray(action, dtype=np.float32)
        if action.shape != (4,) or not np.all(np.isfinite(action)):
            raise ValueError("action must be a finite array with shape (4,)")
        action = np.clip(action, -1.0, 1.0)

        old_tool = self.tool_position
        old_tray = self.tray_position
        old_target_distance = float(np.linalg.norm(old_tray - self.target_position))
        old_pick_distance = float(np.linalg.norm(old_tool - old_tray))

        current_joint_positions = self.data.qpos[self._slide_qpos_adrs].copy()
        target_joint_positions = current_joint_positions + action[:3] * ACTION_STEP_METRES
        target_joint_positions = np.clip(
            target_joint_positions,
            self._slide_ranges[:, 0],
            self._slide_ranges[:, 1],
        )
        self.data.ctrl[self._actuator_ids] = target_joint_positions

        requested_closed = bool(action[3] > 0.0)
        newly_grasped = False
        if requested_closed and not self._gripper_closed and not self._attached:
            newly_grasped = self._try_grasp()
        releasing = self._gripper_closed and not requested_closed and self._attached

        for _ in range(self.frame_skip):
            mujoco.mj_step(self.model, self.data)
            self._follow_tool()

        self._gripper_closed = requested_closed
        if releasing:
            self._success = self._release_is_successful()
            self._dropped = not self._success
            self._attached = False
            self.data.qvel[self._tray_dof_adr : self._tray_dof_adr + 6] = 0.0
            mujoco.mj_forward(self.model, self.data)

        self._elapsed_steps += 1
        terminated = self._success or self._dropped
        truncated = self._elapsed_steps >= self.max_steps and not terminated
        self._episode_done = terminated or truncated

        new_tool = self.tool_position
        new_tray = self.tray_position
        if self._attached:
            progress = old_target_distance - float(
                np.linalg.norm(new_tray - self.target_position)
            )
        else:
            progress = old_pick_distance - float(np.linalg.norm(new_tool - new_tray))
        reward = -0.01 + 4.0 * progress
        if newly_grasped:
            reward += 0.5
        if self._success:
            reward += 10.0
        elif self._dropped:
            reward -= 5.0
        elif truncated:
            reward -= 1.0

        info = {
            "is_success": self._success,
            "is_attached": self._attached,
            "dropped": self._dropped,
            "grasped_this_step": newly_grasped,
            "released_this_step": releasing,
            "distance_to_target": float(np.linalg.norm(new_tray - self.target_position)),
            "domain_parameters": self.domain_parameters.to_dict(),
        }
        observation = self._observation()
        if not self.observation_space.contains(observation):
            raise RuntimeError(f"environment emitted an invalid observation: {observation!r}")
        return observation, float(reward), terminated, truncated, info

    def render(self) -> np.ndarray | None:
        """Render a headless RGB diagnostic projection of the live simulator state."""
        if self.render_mode is None:
            return None
        from simulation.rendering import render_tray_state

        return render_tray_state(self)

    def close(self) -> None:
        """Release resources (the software projection has no native context)."""
        return None
