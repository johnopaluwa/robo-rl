"""Transport-agnostic behaviour shared by the ROS 2 nodes and the web viewer.

The ROS 2 nodes in this package are deliberately thin wrappers: they translate
between ``rclpy`` / ``std_msgs`` and the plain-Python classes below. The web
viewer in ``web/`` drives the exact same classes over an in-process transport.

That sharing is the point. It means a green web demo or a passing
``tools/proof_pipeline.py`` run is real evidence about the decision logic that
executes under ROS 2 -- the only thing that differs between the two is the
transport, not the behaviour. Nothing in this module imports ROS, so it stays
testable (and runnable) without a ROS 2 installation.

See ``docs/VERIFICATION.md`` for what each layer of this does and does not
prove.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Optional

from robo_rl_demo.detection import (
    DEFAULT_MIN_CONFIDENCE,
    Detection,
    finite_number,
    make_demo_detection,
    should_attempt_pick,
)

#: Topic the camera source publishes synthetic detections on.
PICK_TOPIC = "detected_object"

#: Topic operator commands (start/stop/threshold) are published on.
COMMAND_TOPIC = "arm_command"

#: Signature a transport must provide: ``publish(topic, payload) -> None``.
Publisher = Callable[[str, str], None]


def validate_rate_hz(rate_hz: float) -> float:
    """Return a usable publish rate, or raise a useful validation error."""
    value = finite_number(rate_hz, "publish_rate_hz")
    if value <= 0.0:
        raise ValueError("publish_rate_hz must be a finite number greater than zero")
    return value


def validate_topic(topic: str) -> str:
    """Return a non-empty topic name, or raise a useful validation error."""
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("topic must not be empty")
    return topic.strip()


def validate_min_confidence(min_confidence: float) -> float:
    """Return a confidence threshold in [0, 1], or raise a validation error."""
    value = finite_number(min_confidence, "min_confidence")
    if not 0.0 <= value <= 1.0:
        raise ValueError("min_confidence must be between 0 and 1")
    return value


@dataclass(frozen=True)
class PickResult:
    """The outcome of feeding one raw topic payload to :class:`PickerLogic`.

    ``message`` is the exact human-readable line the ROS 2 node logs and the web
    viewer displays, so both surfaces show identical wording.
    """

    detection: Optional[Detection]
    attempted: bool
    message: str
    error: Optional[str] = None

    @property
    def malformed(self) -> bool:
        """True when the payload could not be parsed into a Detection."""
        return self.detection is None


def format_publication(detection: Detection) -> str:
    """Format the log line emitted when a detection is published."""
    return (
        f"Published #{detection.detection_id}: {detection.label} "
        f"at ({detection.x:.3f}, {detection.y:.3f}) m, "
        f"confidence={detection.confidence:.2f}"
    )


def format_pick(detection: Detection) -> str:
    """Format the log line for a detection worth attempting to pick."""
    return (
        f"Would pick #{detection.detection_id} ({detection.label}) at "
        f"({detection.x:.3f}, {detection.y:.3f}) m"
    )


def format_skip(detection: Detection, min_confidence: float) -> str:
    """Format the log line for a detection below the confidence threshold."""
    return (
        f"Skipping #{detection.detection_id} ({detection.label}): "
        f"confidence {detection.confidence:.2f} is below {min_confidence:.2f}"
    )


class CameraSource:
    """Publishes synthetic detections through an injected transport.

    This is the whole of the "fake camera" behaviour: the ROS 2 node only adds
    a parameter lookup, an rclpy publisher and a timer around it.
    """

    def __init__(
        self,
        publish: Publisher,
        *,
        rate_hz: float = 1.0,
        seed: Optional[int] = None,
        topic: str = PICK_TOPIC,
    ) -> None:
        self._publish = publish
        self.rate_hz = validate_rate_hz(rate_hz)
        self.period_s = 1.0 / self.rate_hz
        self.topic = validate_topic(topic)
        self._rng = random.Random(seed)
        self._next_detection_id = 0

    def next_detection(self) -> Detection:
        """Build the next deterministic-if-seeded synthetic observation."""
        detection = make_demo_detection(self._rng, self._next_detection_id)
        self._next_detection_id += 1
        return detection

    def tick(self) -> Detection:
        """Publish one synthetic detection and return it."""
        detection = self.next_detection()
        self._publish(self.topic, detection.to_json())
        return detection


class PickerLogic:
    """Validates detections and decides whether a pick is worth attempting.

    Deliberately ROS-free and side-effect-light: it counts what it saw and calls
    an optional observer, which is all the ROS 2 node and the web viewer need.
    """

    def __init__(
        self,
        *,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        on_result: Optional[Callable[[PickResult], None]] = None,
    ) -> None:
        self.min_confidence = validate_min_confidence(min_confidence)
        self._on_result = on_result
        self.count_attempted = 0
        self.count_skipped = 0
        self.count_malformed = 0

    def set_min_confidence(self, min_confidence: float) -> float:
        """Update the threshold at runtime (the ROS 2 node does this on command)."""
        self.min_confidence = validate_min_confidence(min_confidence)
        return self.min_confidence

    def handle_payload(self, payload: str) -> PickResult:
        """Parse, validate and decide. Never raises on bad input."""
        try:
            detection = Detection.from_json(payload)
        except ValueError as error:
            self.count_malformed += 1
            result = PickResult(
                detection=None,
                attempted=False,
                message=f"Ignoring malformed detection: {error}",
                error=str(error),
            )
        else:
            attempted = should_attempt_pick(detection, self.min_confidence)
            if attempted:
                self.count_attempted += 1
                message = format_pick(detection)
            else:
                self.count_skipped += 1
                message = format_skip(detection, self.min_confidence)
            result = PickResult(detection=detection, attempted=attempted, message=message)

        if self._on_result is not None:
            self._on_result(result)
        return result


VALID_COMMAND_ACTIONS = ("start", "stop", "call_support", "set_min_confidence")


@dataclass(frozen=True)
class OperatorCommand:
    """A parsed operator command, as sent by the web viewer's buttons.

    The same JSON schema travels over ROS 2 (``std_msgs/String`` on
    ``arm_command``) and over the web viewer's WebSocket, so one parser covers
    both surfaces in :func:`parse_command`.
    """

    action: str
    value: Optional[float] = None


def parse_command(payload: str) -> OperatorCommand:
    """Parse an operator command payload, raising ValueError on bad input."""
    import json  # local import keeps the module's import list small and obvious

    try:
        decoded = json.loads(payload)
    except (json.JSONDecodeError, TypeError) as error:
        raise ValueError("command must be valid JSON") from error

    if not isinstance(decoded, dict):
        raise ValueError("command must be a JSON object")

    action = decoded.get("action")
    if action not in VALID_COMMAND_ACTIONS:
        raise ValueError(
            f"action must be one of: {', '.join(VALID_COMMAND_ACTIONS)}"
        )

    value = decoded.get("value")
    if action == "set_min_confidence":
        if value is None:
            raise ValueError("set_min_confidence requires a value")
        value = validate_min_confidence(value)
    elif value is not None:
        value = finite_number(value, "value")

    return OperatorCommand(action=action, value=value)


def simulate_grasp(confidence: float, rng: random.Random) -> bool:
    """Return whether a simulated grasp succeeds, given detection confidence.

    Not used by the ROS 2 nodes (they have no arm yet). It exists so the web
    viewer and the proof script can model a plausible relationship between
    detection confidence and grasp success -- which is exactly the trade-off the
    ``min_confidence`` threshold is for. It is a teaching model, not a policy.
    """
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    return rng.random() < (0.35 + 0.65 * confidence)
