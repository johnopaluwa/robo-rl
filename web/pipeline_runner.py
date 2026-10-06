"""Drives the shared pipeline and keeps the state the browser renders.

In ``sim`` mode this owns a tiny world model (objects appearing, an arm moving,
bins filling) purely so the pipeline's decisions are visible. In ``ros2`` mode
it owns nothing: it mirrors real DDS detections, runs them through the *same*
:class:`~robo_rl_demo.picker.PickerLogic`, and publishes operator commands onto
``arm_command`` for the real picker node to act on.

Every log line shown in the browser comes from the shared pipeline module, so
what you read on screen is what a ROS 2 node would log.
"""

from __future__ import annotations

import random
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional

from robo_rl_demo.detection import DEFAULT_MIN_CONFIDENCE, Detection
from robo_rl_demo.pipeline import (
    COMMAND_TOPIC,
    PICK_TOPIC,
    CameraSource,
    OperatorCommand,
    PickResult,
    PickerLogic,
    format_publication,
    parse_command,
    simulate_grasp,
    validate_rate_hz,
)
from transports import ros_available

MAX_LOG_LINES = 60

#: Seconds each phase of the simulated pick cycle takes. Purely cosmetic: this
#: is what makes the pipeline's decisions visible on screen.
PHASE_DURATIONS = {"approach": 0.30, "carry": 0.40, "settle": 0.30}
PHASE_ORDER = ("approach", "carry", "settle")


@dataclass
class LogLine:
    """One timestamped line of the console the browser shows."""

    at: float
    level: str
    text: str

    def to_dict(self, started_at: float) -> dict:
        return {
            "t": round(self.at - started_at, 3),
            "level": self.level,
            "text": self.text,
        }


@dataclass
class SimObject:
    """A simulated object moving through the pick cycle."""

    detection: Detection
    phase: str = "approach"
    elapsed: float = 0.0
    attempted: bool = False
    success: Optional[bool] = None
    destination: Optional[str] = None

    @property
    def progress(self) -> float:
        duration = PHASE_DURATIONS.get(self.phase, 1.0)
        return min(1.0, self.elapsed / duration) if duration else 1.0


@dataclass
class Counters:
    published: int = 0
    attempted: int = 0
    skipped: int = 0
    malformed: int = 0
    placed: int = 0
    dropped: int = 0
    needs_review: int = 0
    support_requests: int = 0
    commands_sent: int = 0


class PipelineRunner:
    """Thread-safe owner of pipeline state, stepped by the web server's loop."""

    def __init__(
        self,
        transport,
        *,
        rate_hz: float = 1.0,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        seed: Optional[int] = 42,
        auto_pause_on_review: bool = False,
        topic: str = PICK_TOPIC,
        command_topic: str = COMMAND_TOPIC,
    ) -> None:
        self._lock = threading.RLock()
        self.transport = transport
        self.mode = transport.mode
        self.topic = topic
        self.command_topic = command_topic

        self.seed = seed
        self.rate_hz = rate_hz
        self.auto_pause_on_review = auto_pause_on_review
        self.running = True
        self.pause_reason: Optional[str] = None
        self.started_at = time.monotonic()
        self.tick = 0
        self.publish_accumulator = 0.0
        self.counters = Counters()
        self.objects: List[SimObject] = []
        #: "review" collects low-confidence items that needed a human; a failed
        #: grasp leaves the item where it was, so it fills no bin.
        self.bins: Dict[str, int] = {
            label: 0 for label in ("item_a", "item_b", "item_c", "review")
        }
        self.confidence_history: Deque[float] = deque(maxlen=80)
        self.log: Deque[LogLine] = deque(maxlen=MAX_LOG_LINES)
        self._rng = random.Random(seed)

        self.logic = PickerLogic(
            min_confidence=min_confidence, on_result=self._on_pick_result
        )
        self.camera = CameraSource(
            self.transport.publish,
            rate_hz=rate_hz,
            seed=seed,
            topic=topic,
        )

        # The picker is a subscriber in *both* modes. In sim mode this is a
        # modelled topic, in ros2 mode real DDS -- but the data path is
        # identical: camera -> topic -> picker -> decision.
        self.transport.subscribe(self.topic, self._on_message)

        self._remember("info", "Pipeline runner started")
        self._remember("info", f"Transport: {transport.label}")
        if self.mode == "sim":
            self._remember(
                "warn",
                "Simulation mode: ROS 2 is NOT running. This proves the pipeline "
                "logic and wiring, not DDS.",
            )
            self._remember(
                "info",
                f"Threshold {self.logic.min_confidence:.2f}; camera publishing "
                f"on '{self.topic}' at {rate_hz:g} Hz",
            )
        else:
            self._remember("good", f"Subscribed to live ROS 2 topic '{self.topic}'")

    # -- logging -------------------------------------------------------------
    def _remember(self, level: str, text: str) -> None:
        with self._lock:
            self.log.append(LogLine(at=time.monotonic(), level=level, text=text))

    # -- pipeline callbacks --------------------------------------------------
    def _on_pick_result(self, result: PickResult) -> None:
        """Called by the shared PickerLogic for every payload it sees."""
        with self._lock:
            if result.malformed:
                self.counters.malformed += 1
                self._remember("error", result.message)
                return

            detection = result.detection
            assert detection is not None  # malformed handled above
            self.confidence_history.append(detection.confidence)

            if not result.attempted:
                self.counters.skipped += 1
                self.counters.needs_review += 1
                self._remember("warn", result.message)
                if self.mode == "sim":
                    sim_object = self._find(detection.detection_id)
                    if sim_object is not None:
                        sim_object.attempted = False
                        sim_object.destination = "review"
                        sim_object.success = False
                if self.auto_pause_on_review and self.mode == "sim":
                    self.running = False
                    self.pause_reason = f"awaiting human review of #{detection.detection_id}"
                    self._remember(
                        "warn", "Line paused: low-confidence item needs a human (teleop fallback)"
                    )
                return

            self.counters.attempted += 1
            self._remember("info", result.message)
            if self.mode == "sim":
                sim_object = self._find(detection.detection_id)
                if sim_object is not None:
                    sim_object.attempted = True
                    sim_object.success = simulate_grasp(detection.confidence, self._rng)
                    sim_object.destination = (
                        detection.label if sim_object.success else None
                    )

    def _find(self, detection_id: int) -> Optional[SimObject]:
        for sim_object in self.objects:
            if sim_object.detection.detection_id == detection_id:
                return sim_object
        return None

    def _on_message(self, payload: str) -> None:
        """Subscriber callback: the same entry point in sim and ros2 modes."""
        if not self.running:
            self._remember("info", "Hold: operator stop is active; message ignored")
            return
        self.logic.handle_payload(payload)

    # -- world stepping ------------------------------------------------------
    def step(self, dt: float) -> None:
        """Advance the simulation and publish detections on the camera's cadence."""
        with self._lock:
            self.tick += 1
            if self.mode != "sim":
                return
            if self.running:
                self.publish_accumulator += dt
                while self.publish_accumulator >= self.camera.period_s:
                    self.publish_accumulator -= self.camera.period_s
                    self._publish_one()
            for sim_object in list(self.objects):
                sim_object.elapsed += dt
                if sim_object.elapsed < PHASE_DURATIONS[sim_object.phase]:
                    continue
                sim_object.elapsed = 0.0
                if sim_object.phase == "approach":
                    sim_object.phase = "carry"
                elif sim_object.phase == "carry":
                    sim_object.phase = "settle"
                    self._resolve(sim_object)
                else:
                    self.objects.remove(sim_object)

    def _publish_one(self) -> None:
        """Register the object *before* publishing, so the decision can find it.

        The decision callback runs synchronously inside ``publish`` (in sim mode
        the transport is in-process), so the world model has to exist first.
        """
        detection = self.camera.next_detection()
        sim_object = SimObject(detection=detection)
        self.objects.append(sim_object)
        self.counters.published += 1
        self._remember("info", format_publication(detection))
        self.transport.publish(self.camera.topic, detection.to_json())

    def _resolve(self, sim_object: SimObject) -> None:
        """An object finished its cycle: count it and say where it went."""
        detection = sim_object.detection
        if sim_object.success is None and sim_object.destination is None:
            # The line was stopped or paused mid-cycle, so nothing was decided.
            self._remember(
                "info",
                f"Aborted #{detection.detection_id} ({detection.label}): "
                "no decision was made before the line stopped",
            )
            return
        if sim_object.destination == "review":
            self.bins["review"] += 1
            return
        if sim_object.success:
            self.bins[detection.label] += 1
            self.counters.placed += 1
            self._remember(
                "good",
                f"Placed #{detection.detection_id} ({detection.label}) "
                f"in bin {detection.label}",
            )
        else:
            self.counters.dropped += 1
            self._remember(
                "warn",
                f"Dropped #{detection.detection_id} ({detection.label}) -- "
                f"grasp failed at confidence {detection.confidence:.2f}",
            )

    # -- operator commands ---------------------------------------------------
    def handle_command(self, payload: str) -> dict:
        """Apply a command from the browser; same JSON schema as over ROS 2."""
        try:
            command = parse_command(payload)
        except ValueError as error:
            self._remember("error", f"Rejected command: {error}")
            raise
        self._apply(command)
        return {"ok": True, "action": command.action}

    def _apply(self, command: OperatorCommand) -> None:
        with self._lock:
            if self.mode == "ros2":
                # Publish to the real node; the local echo below is UI feedback.
                self.transport.publish(self.command_topic, self._command_json(command))
                self.counters.commands_sent += 1

            if command.action == "start":
                self.running = True
                self.pause_reason = None
                self._remember("good", "START: picking enabled")
            elif command.action == "stop":
                self.running = False
                self.pause_reason = "operator stop"
                self._remember("warn", "STOP: picking disabled by operator")
            elif command.action == "set_min_confidence":
                threshold = self.logic.set_min_confidence(command.value)
                self._remember("info", f"Minimum confidence set to {threshold:.2f}")
            elif command.action == "call_support":
                self.counters.support_requests += 1
                self._remember(
                    "warn",
                    "CALL SUPPORT: teleop fallback engaged -- this is the "
                    "intervention the Wizard-of-Oz pilot counts",
                )

    @staticmethod
    def _command_json(command: OperatorCommand) -> str:
        import json

        body = {"action": command.action}
        if command.value is not None:
            body["value"] = command.value
        return json.dumps(body, separators=(",", ":"))

    def configure(
        self,
        *,
        rate_hz: Optional[float] = None,
        auto_pause_on_review: Optional[bool] = None,
        reset: bool = False,
    ) -> dict:
        """Change simulation-only knobs from the browser (sim mode only)."""
        with self._lock:
            if self.mode != "sim":
                raise ValueError("these controls are simulation-only")
            if rate_hz is not None:
                rate = validate_rate_hz(rate_hz)
                self.camera.rate_hz = rate
                self.camera.period_s = 1.0 / rate
                self.publish_accumulator = 0.0
                self._remember("info", f"Camera rate set to {rate:g} Hz")
            if auto_pause_on_review is not None:
                self.auto_pause_on_review = bool(auto_pause_on_review)
                self._remember(
                    "info",
                    "Auto-pause on review "
                    f"{'enabled' if self.auto_pause_on_review else 'disabled'}",
                )
            if reset:
                self.counters = Counters()
                self.objects.clear()
                for label in self.bins:
                    self.bins[label] = 0
                self.confidence_history.clear()
                self.log.clear()
                self.logic = PickerLogic(
                    min_confidence=self.logic.min_confidence,
                    on_result=self._on_pick_result,
                )
                self.running = True
                self.pause_reason = None
                self._remember("good", "Counters and counters reset for a clean run")
            return {"ok": True, "reset": reset}

    def timeout_review(self, resolve: bool = True) -> None:
        """Operator resolved a flagged item; resume if the line was auto-paused."""
        with self._lock:
            if self.auto_pause_on_review and self.pause_reason and "review" in self.pause_reason:
                self.running = True
                self.pause_reason = None
                self._remember("good", "Review resolved: line resumed")

    # -- snapshot for the browser -------------------------------------------
    def snapshot(self) -> dict:
        with self._lock:
            uptime = time.monotonic() - self.started_at
            total_decisions = self.counters.attempted + self.counters.skipped
            placed_total = self.counters.placed + self.counters.dropped
            current = None
            for sim_object in reversed(self.objects):
                current = {
                    "id": sim_object.detection.detection_id,
                    "label": sim_object.detection.label,
                    "x": sim_object.detection.x,
                    "y": sim_object.detection.y,
                    "confidence": sim_object.detection.confidence,
                    "phase": sim_object.phase,
                    "progress": round(sim_object.progress, 3),
                    "attempted": sim_object.attempted,
                    "success": sim_object.success,
                    "destination": sim_object.destination,
                }
                break

            return {
                "mode": self.mode,
                "mode_label": self.transport.label,
                "is_real_ros": self.transport.is_real_ros,
                "ros_available": ros_available(),
                "running": self.running,
                "pause_reason": self.pause_reason,
                "uptime_s": round(uptime, 2),
                "tick": self.tick,
                "config": {
                    "rate_hz": self.camera.rate_hz,
                    "min_confidence": self.logic.min_confidence,
                    "seed": self.seed,
                    "auto_pause_on_review": self.auto_pause_on_review,
                    "topic": self.topic,
                    "command_topic": self.command_topic,
                },
                "counters": {
                    **self.counters.__dict__,
                    "decisions": total_decisions,
                },
                "rates": {
                    "success": round(self.counters.placed / placed_total, 3)
                    if placed_total
                    else None,
                    "review": round(self.counters.needs_review / total_decisions, 3)
                    if total_decisions
                    else None,
                },
                "current": current,
                "objects": [
                    {
                        "id": o.detection.detection_id,
                        "label": o.detection.label,
                        "x": o.detection.x,
                        "y": o.detection.y,
                        "confidence": o.detection.confidence,
                        "phase": o.phase,
                        "progress": round(o.progress, 3),
                        "destination": o.destination,
                        "success": o.success,
                    }
                    for o in self.objects
                    if o.phase in PHASE_ORDER
                ],
                "bins": dict(self.bins),
                "confidence_history": [round(c, 3) for c in self.confidence_history],
                "log": [line.to_dict(self.started_at) for line in list(self.log)[-40:]],
                "graph": self.transport.graph(),
            }
