"""Reproducible domain-parameter sampling for the tray-loading task.

This module intentionally depends only on the Python standard library so the
randomization ranges and their tests remain usable without MuJoCo or PyTorch.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol


class UniformRandom(Protocol):
    """The small RNG interface used by both ``random.Random`` and NumPy RNGs."""

    def uniform(self, low: float, high: float) -> float: ...


@dataclass(frozen=True)
class DomainParameters:
    """Physical and visual parameters sampled once per episode.

    Coordinates are metres in the MuJoCo scene. ``tray_scale`` scales the
    tray's horizontal footprint (its thickness and mass stay fixed); friction
    is the MuJoCo sliding-friction coefficient; lighting is a diffuse-light
    multiplier. Keeping the sampled values explicit makes each reset auditable.
    """

    source_x: float
    source_y: float
    target_x: float
    target_y: float
    tray_scale: float
    friction: float
    light_intensity: float

    def to_dict(self) -> dict[str, float]:
        """Return a JSON-friendly representation with stable field names."""
        return asdict(self)


def sample_domain_parameters(rng: UniformRandom) -> DomainParameters:
    """Sample one plausible bakery-tray scene from fixed, documented ranges."""
    return DomainParameters(
        source_x=rng.uniform(-0.36, -0.22),
        source_y=rng.uniform(-0.18, 0.18),
        target_x=rng.uniform(0.22, 0.36),
        target_y=rng.uniform(-0.18, 0.18),
        tray_scale=rng.uniform(0.85, 1.15),
        friction=rng.uniform(0.55, 1.35),
        light_intensity=rng.uniform(0.65, 1.0),
    )
