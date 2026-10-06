#!/usr/bin/env python3
"""Live ROS 2 smoke test: the only thing that can verify the ROS 2 milestone.

This runs *real* nodes and asserts on the real graph:

1. ``fake_camera`` publishes detections that arrive over DDS at an observer node.
2. Every received payload parses with the shared schema.
3. ``picker`` decided on every message it received (no silent drops).
4. The picker's threshold is the one that was configured.
5. STOP / START commands published on ``arm_command`` actually change the node.

Requires a sourced ROS 2 installation. Exit codes: 0 pass, 1 fail, 3 skipped
(no rclpy) -- so callers can tell "not verified" apart from "verified broken".

    source /opt/ros/jazzy/setup.bash
    python3 tools/ros2_smoke_test.py --seconds 6 --rate 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
PACKAGE_ROOT = os.path.join(REPO_ROOT, "ros2_ws", "src", "robo_rl_demo")
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)
DEFAULT_ARTIFACTS = os.path.join(REPO_ROOT, "artifacts", "proofs")

try:
    import rclpy
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.node import Node
    from std_msgs.msg import String
except Exception as error:  # pragma: no cover - depends on the machine
    print("SKIP: rclpy is not importable, so the ROS 2 milestone cannot be verified here.")
    print(f"      import error: {error}")
    print()
    print("      To verify it for real, on a machine with ROS 2 installed:")
    print("        source /opt/ros/jazzy/setup.bash     # Humble or Jazzy")
    print("        cd ros2_ws && colcon build --symlink-install --packages-select robo_rl_demo")
    print("        cd .. && python3 tools/ros2_smoke_test.py")
    print()
    print("      Until that passes, MILESTONES.md keeps the ROS 2 checkbox unchecked.")
    raise SystemExit(3)

from robo_rl_demo.detection import Detection  # noqa: E402
from robo_rl_demo.fake_camera import FakeCameraNode  # noqa: E402
from robo_rl_demo.picker import PickerNode  # noqa: E402


class Observer(Node):
    """Watches the topic from outside, like a third party on the graph."""

    def __init__(self, topic: str) -> None:
        super().__init__("smoke_observer")
        self.received: list[str] = []
        self.bad_payloads: list[str] = []
        self._sub = self.create_subscription(String, topic, self._on_message, 10)

    def _on_message(self, message: String) -> None:
        self.received.append(message.data)
        try:
            Detection.from_json(message.data)
        except ValueError:
            self.bad_payloads.append(message.data)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ROS 2 smoke test for robo_rl_demo")
    parser.add_argument("--seconds", type=float, default=6.0)
    parser.add_argument("--rate", type=float, default=5.0, help="camera publish rate (Hz)")
    parser.add_argument("--threshold", type=float, default=0.65)
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACTS)
    args = parser.parse_args(argv)

    checks: list[dict] = []
    started = datetime.now(timezone.utc)

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "passed": bool(ok), "detail": detail})

    distro = os.environ.get("ROS_DISTRO", "unknown")
    check("rclpy imported and a ROS distro is sourced", distro != "unknown", f"ROS_DISTRO={distro}")

    rclpy.init(args=["--ros-args", "-p", f"publish_rate_hz:={args.rate}",
                     "-p", f"min_confidence:={args.threshold}"])
    executor = None
    try:
        camera = FakeCameraNode()
        picker = PickerNode()
        observer = Observer("detected_object")
        check("all three nodes constructed", True, "fake_camera, picker, smoke_observer")

        executor = MultiThreadedExecutor()
        for node in (camera, picker, observer):
            executor.add_node(node)
        thread = threading.Thread(target=executor.spin, name="ros2-executor", daemon=True)
        thread.start()

        # Give discovery a moment, then inspect the real graph.
        time.sleep(2.0)
        publishers = observer.get_publishers_info_by_topic("detected_object")
        subscribers = observer.get_subscriptions_info_by_topic("detected_object")
        check(
            "topic discovered with a publisher and a subscriber",
            len(publishers) >= 1 and len(subscribers) >= 1,
            f"{len(publishers)} publisher(s), {len(subscribers)} subscriber(s)",
        )

        time.sleep(max(0.0, args.seconds - 2.0))
        received = len(observer.received)
        expected = max(1, int(args.rate * args.seconds * 0.6))  # tolerate startup latency
        check(
            "detections arrived over DDS",
            received >= expected,
            f"{received} messages (expected >= {expected})",
        )
        check(
            "every payload satisfied the shared detection schema",
            not observer.bad_payloads,
            f"{len(observer.bad_payloads)} invalid payload(s)",
        )

        stats = picker.stats
        check(
            "picker decided on the messages it received",
            stats["decisions"] >= received * 0.9,
            f"{stats['decisions']} decisions for {received} received",
        )
        check(
            "picker used the configured threshold",
            abs(stats["min_confidence"] - args.threshold) < 1e-6,
            f"min_confidence={stats['min_confidence']}, attempted={stats['attempted']}, "
            f"skipped={stats['skipped']}",
        )

        # Command round-trip through real DDS, exactly what the browser does.
        commander = Node("smoke_commander")
        executor.add_node(commander)
        publisher = commander.create_publisher(String, "arm_command", 10)

        def send(action: str) -> None:
            message = String()
            message.data = json.dumps({"action": action})
            publisher.publish(message)

        time.sleep(0.5)
        send("stop")
        time.sleep(1.5)
        check("STOP command over DDS disabled picking", picker.stats["enabled"] is False)

        send("start")
        time.sleep(1.5)
        check("START command over DDS re-enabled picking", picker.stats["enabled"] is True)

        send("set_min_confidence")  # no value: must be ignored, not crash
        time.sleep(1.0)
        check(
            "malformed command was ignored without changing state",
            abs(picker.stats["min_confidence"] - args.threshold) < 1e-6,
        )
    finally:
        if executor is not None:
            executor.shutdown(timeout_sec=2.0)
        if rclpy.ok():
            rclpy.shutdown()

    passed = sum(1 for c in checks if c["passed"])
    failed = len(checks) - passed
    verdict = "PASS" if failed == 0 else "FAIL"

    artifact = {
        "proof": "ros2-smoke",
        "verdict": verdict,
        "transport": "real ROS 2 / rclpy / DDS",
        "ros_distro": distro,
        "proves": [
            "a real rclpy publisher and subscriber exchange messages over DDS",
            "the shared schema validates payloads that crossed the wire",
            "operator commands change real node behaviour",
        ],
        "does_not_prove": [
            "anything about physical hardware (no arm is attached)",
            "behaviour under load, or with a real camera",
        ],
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "checks_passed": passed,
        "checks_failed": failed,
        "checks": checks,
    }
    os.makedirs(args.artifact_dir, exist_ok=True)
    path = os.path.join(args.artifact_dir, "ros2_smoke.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2)

    print(f"proof: ros2-smoke  transport: real ROS 2 ({distro})")
    for item in checks:
        flag = "PASS" if item["passed"] else "FAIL"
        detail = f"  ({item['detail']})" if item["detail"] else ""
        print(f"  [{flag}] {item['check']}{detail}")
    print()
    print(f"  {verdict}: {passed}/{len(checks)} checks | artifact: "
          f"{os.path.relpath(path, REPO_ROOT)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
