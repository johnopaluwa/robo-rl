"""ROS-independent data model and decisions for the synthetic camera demo.

The message intentionally uses a small JSON schema carried by ``std_msgs/String``
so the example can be tested without a ROS installation or custom interface build.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from typing import Any


DEMO_LABELS = ("item_a", "item_b", "item_c")
DEFAULT_MIN_CONFIDENCE = 0.65


def finite_number(value: Any, field_name: str) -> float:
    """Return a finite float or raise a useful validation error.

    Public because the shared pipeline (and the web viewer built on it) needs the
    same validation rules as the ROS 2 nodes.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    try:
        number = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{field_name} must be a finite number") from error
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be a finite number")
    return number


@dataclass(frozen=True)
class Detection:
    """A toy 2-D detection, with coordinates expressed in metres."""

    detection_id: int
    label: str
    x: float
    y: float
    confidence: float

    def __post_init__(self) -> None:
        if isinstance(self.detection_id, bool) or not isinstance(
            self.detection_id, int
        ):
            raise ValueError("id must be an integer")
        if self.detection_id < 0:
            raise ValueError("id must be zero or greater")
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("label must be a non-empty string")

        object.__setattr__(self, "x", finite_number(self.x, "x"))
        object.__setattr__(self, "y", finite_number(self.y, "y"))
        confidence = finite_number(self.confidence, "confidence")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "confidence", confidence)

    def to_json(self) -> str:
        """Serialize this detection into the topic's stable JSON payload."""
        return json.dumps(
            {
                "id": self.detection_id,
                "label": self.label,
                "x": self.x,
                "y": self.y,
                "confidence": self.confidence,
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, payload: str) -> Detection:
        """Parse and validate a detection received from the ROS topic."""
        try:
            decoded = json.loads(payload)
        except (json.JSONDecodeError, TypeError) as error:
            raise ValueError("payload must be valid JSON") from error

        if not isinstance(decoded, dict):
            raise ValueError("payload must be a JSON object")

        required_fields = {"id", "label", "x", "y", "confidence"}
        missing_fields = sorted(required_fields - decoded.keys())
        if missing_fields:
            raise ValueError(f"missing required field(s): {', '.join(missing_fields)}")

        return cls(
            detection_id=decoded["id"],
            label=decoded["label"],
            x=decoded["x"],
            y=decoded["y"],
            confidence=decoded["confidence"],
        )


def make_demo_detection(rng: random.Random, detection_id: int) -> Detection:
    """Make a deterministic-if-seeded synthetic camera observation."""
    return Detection(
        detection_id=detection_id,
        label=rng.choice(DEMO_LABELS),
        x=round(rng.uniform(-0.25, 0.25), 3),
        y=round(rng.uniform(-0.25, 0.25), 3),
        confidence=round(rng.uniform(0.35, 1.0), 3),
    )


def should_attempt_pick(
    detection: Detection, min_confidence: float = DEFAULT_MIN_CONFIDENCE
) -> bool:
    """Return whether the demo picker should attempt a *simulated* pick."""
    threshold = finite_number(min_confidence, "min_confidence")
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("min_confidence must be between 0 and 1")
    return detection.confidence >= threshold
