"""Dependency-light 2D diagnostic renderer for MuJoCo episode recordings.

This is a software projection of the live MuJoCo state, not a photorealistic
MuJoCo/OpenGL renderer. The two panels show a top-down workspace and an x/z
side elevation so headless CI and laptops without a GL context can still record
what the simulator did.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np


class RenderableTrayEnv(Protocol):
    model: object
    domain_parameters: object
    _tray_geom_id: int
    _elapsed_steps: int
    _gripper_closed: bool
    _attached: bool

    @property
    def tool_position(self) -> np.ndarray: ...

    @property
    def tray_position(self) -> np.ndarray: ...

    @property
    def target_position(self) -> np.ndarray: ...


def render_tray_state(env: RenderableTrayEnv) -> np.ndarray:
    """Project the current MuJoCo state into an 800×500 RGB diagnostic frame."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as error:  # pragma: no cover - supplied by gymnasium[mujoco]
        raise RuntimeError("RGB rendering needs Pillow; install simulation/requirements-sim.txt") from error

    width, height = 800, 500
    image = Image.new("RGB", (width, height), (241, 244, 247))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    draw.text((22, 12), "MuJoCo bakery tray loading", fill=(28, 39, 50), font=font)
    draw.text(
        (22, 31),
        "Diagnostic software projection - MuJoCo tray physics; Cartesian tool + virtual grasp",
        fill=(78, 89, 99),
        font=font,
    )

    # Left panel: top-down x/y view of the table/workspace.
    top_panel = (20, 62, 550, 456)
    draw.rounded_rectangle(top_panel, radius=8, fill=(255, 255, 255), outline=(194, 201, 208), width=1)
    top_left, top_top, top_right, top_bottom = top_panel
    top_center_x = (top_left + top_right) / 2
    top_center_y = (top_top + top_bottom) / 2
    top_scale = min(
        (top_right - top_left - 42) / 1.30,
        (top_bottom - top_top - 54) / 0.84,
    )

    def top_xy(x: float, y: float) -> tuple[float, float]:
        return top_center_x + x * top_scale, top_center_y - y * top_scale

    table_tl = top_xy(-0.65, 0.42)
    table_br = top_xy(0.65, -0.42)
    draw.rounded_rectangle(
        (table_tl[0], table_tl[1], table_br[0], table_br[1]),
        radius=8,
        fill=(208, 184, 148),
        outline=(136, 112, 83),
        width=2,
    )
    draw.text((top_left + 12, top_top + 9), "Top-down: x / y (metres)", fill=(41, 52, 61), font=font)

    params = env.domain_parameters
    source_px = top_xy(float(params.source_x), float(params.source_y))
    draw.ellipse(
        (source_px[0] - 8, source_px[1] - 8, source_px[0] + 8, source_px[1] + 8),
        fill=(202, 77, 66),
        outline=(255, 255, 255),
        width=2,
    )
    draw.text((source_px[0] - 23, source_px[1] + 11), "pickup", fill=(130, 49, 44), font=font)

    target_px = top_xy(float(params.target_x), float(params.target_y))
    target_radius = 0.155 * top_scale
    draw.ellipse(
        (
            target_px[0] - target_radius,
            target_px[1] - target_radius,
            target_px[0] + target_radius,
            target_px[1] + target_radius,
        ),
        fill=(188, 231, 197),
        outline=(35, 139, 72),
        width=2,
    )
    draw.text((target_px[0] - 20, target_px[1] + target_radius + 3), "drop zone", fill=(35, 105, 58), font=font)

    tray = env.tray_position
    half_size = env.model.geom_size[env._tray_geom_id]
    tray_px = top_xy(float(tray[0]), float(tray[1]))
    tray_dx = float(half_size[0]) * top_scale
    tray_dy = float(half_size[1]) * top_scale
    draw.rectangle(
        (tray_px[0] - tray_dx, tray_px[1] - tray_dy, tray_px[0] + tray_dx, tray_px[1] + tray_dy),
        fill=(186, 193, 204),
        outline=(55, 66, 79),
        width=2,
    )

    tool = env.tool_position
    tool_px = top_xy(float(tool[0]), float(tool[1]))
    tool_radius = max(5, 0.025 * top_scale)
    if env._attached:
        draw.line((tool_px[0], tool_px[1], tray_px[0], tray_px[1]), fill=(35, 83, 153), width=2)
    draw.ellipse(
        (tool_px[0] - tool_radius, tool_px[1] - tool_radius, tool_px[0] + tool_radius, tool_px[1] + tool_radius),
        fill=(47, 115, 204),
        outline=(255, 255, 255),
        width=2,
    )
    draw.text((tool_px[0] + 8, tool_px[1] - 17), f"tool z={tool[2]:.2f}m", fill=(34, 76, 140), font=font)

    # Right panel: x/z elevation exposes the lift phase hidden by the top view.
    side_panel = (566, 62, 780, 456)
    draw.rounded_rectangle(side_panel, radius=8, fill=(255, 255, 255), outline=(194, 201, 208), width=1)
    side_left, side_top, side_right, side_bottom = side_panel
    side_scale_x = (side_right - side_left - 36) / 1.30
    side_scale_z = (side_bottom - side_top - 70) / 0.58
    side_center_x = (side_left + side_right) / 2
    side_floor_y = side_bottom - 26
    z_min = 0.54

    def side_xz(x: float, z: float) -> tuple[float, float]:
        return side_center_x + x * side_scale_x, side_floor_y - (z - z_min) * side_scale_z

    draw.text((side_left + 11, side_top + 9), "Side: x / z", fill=(41, 52, 61), font=font)
    table_side_tl = side_xz(-0.65, 0.60)
    table_side_br = side_xz(0.65, 0.56)
    draw.rectangle(
        (table_side_tl[0], table_side_tl[1], table_side_br[0], table_side_br[1]),
        fill=(178, 146, 108),
        outline=(136, 112, 83),
    )
    source_side = side_xz(float(params.source_x), 0.612)
    target_side = side_xz(float(params.target_x), 0.612)
    draw.line((source_side[0], source_side[1] - 6, source_side[0], table_side_br[1]), fill=(202, 77, 66), width=2)
    draw.line((target_side[0], target_side[1] - 6, target_side[0], table_side_br[1]), fill=(35, 139, 72), width=2)

    tray_side = side_xz(float(tray[0]), float(tray[2]))
    tray_half_x = float(half_size[0]) * side_scale_x
    tray_half_z = float(half_size[2]) * side_scale_z
    draw.rectangle(
        (
            tray_side[0] - tray_half_x,
            tray_side[1] - tray_half_z,
            tray_side[0] + tray_half_x,
            tray_side[1] + tray_half_z,
        ),
        fill=(186, 193, 204),
        outline=(55, 66, 79),
    )
    tool_side = side_xz(float(tool[0]), float(tool[2]))
    draw.ellipse(
        (tool_side[0] - 6, tool_side[1] - 6, tool_side[0] + 6, tool_side[1] + 6),
        fill=(47, 115, 204),
        outline=(255, 255, 255),
        width=2,
    )
    draw.text((side_left + 11, side_bottom - 19), "tabletop z=0.60m", fill=(78, 89, 99), font=font)

    gripper = "CLOSED" if env._gripper_closed else "OPEN"
    attached = "attached" if env._attached else "free"
    footer = (
        f"step {env._elapsed_steps}   gripper {gripper}   tray {attached}   "
        f"scale {params.tray_scale:.2f}   friction {params.friction:.2f}"
    )
    draw.text((22, 470), footer, fill=(45, 55, 65), font=font)
    return np.asarray(image, dtype=np.uint8)
