"""Transports: how payloads move in each mode.

Both transports expose the same two calls the pipeline needs --
``publish(topic, payload)`` and ``subscribe(topic, callback)`` -- so
:class:`~robo_rl_demo.pipeline.CameraSource` and
:class:`~robo_rl_demo.pipeline.PickerLogic` do not know or care which one is in
use. Swapping the transport swaps simulation for real DDS traffic and nothing
else.

Honesty note: ``SimTransport`` is a plain in-process broker. A green demo in
sim mode proves *logic and wiring*, never that ROS 2 works. ``RosTransport`` is
the only mode that proves ROS 2, and it can only run where ``rclpy`` is
installed. The web viewer always shows which one is live -- see
``docs/VERIFICATION.md``.
"""

from __future__ import annotations

import threading
from typing import Callable, Dict, List, Optional

Subscriber = Callable[[str], None]


class SimTransport:
    """In-process publish/subscribe broker with a ROS-shaped interface."""

    mode = "sim"
    label = "in-process simulation (no DDS, no ROS 2)"
    is_real_ros = False

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: Dict[str, List[Subscriber]] = {}
        self.published_count: Dict[str, int] = {}

    def publish(self, topic: str, payload: str) -> None:
        with self._lock:
            self.published_count[topic] = self.published_count.get(topic, 0) + 1
            subscribers = list(self._subscribers.get(topic, ()))
        for callback in subscribers:
            callback(payload)

    def subscribe(self, topic: str, callback: Subscriber) -> None:
        with self._lock:
            self._subscribers.setdefault(topic, []).append(callback)

    def start(self) -> None:
        """Nothing to spin up for an in-process broker."""

    def stop(self) -> None:
        """Nothing to tear down for an in-process broker."""

    def graph(self) -> dict:
        """Describe the modelled ROS 2 graph, since there is no real one."""
        with self._lock:
            counts = dict(self.published_count)
        return {
            "is_real": False,
            "nodes": [
                {"name": "fake_camera", "role": "publisher", "state": "modelled"},
                {"name": "picker", "role": "subscriber", "state": "modelled"},
                {"name": "web_viewer", "role": "bridge", "state": "active"},
            ],
            "topics": [
                {
                    "name": "/detected_object",
                    "type": "std_msgs/String",
                    "published": counts.get("detected_object", 0),
                },
                {
                    "name": "/arm_command",
                    "type": "std_msgs/String",
                    "published": counts.get("arm_command", 0),
                },
            ],
            "note": "Modelled graph. Not an rclpy graph -- ROS 2 is not running.",
        }


class RosTransport:
    """Real ROS 2 transport built on rclpy.

    Only constructed when ``rclpy`` imports successfully; the web server refuses
    to start in ros2 mode otherwise rather than silently degrading to simulation.
    This code path cannot be exercised in an environment without ROS 2, so
    ``tools/verify.sh --ros2`` exists to confirm it on a machine that has it.
    """

    mode = "ros2"
    label = "rclpy / DDS (real ROS 2)"
    is_real_ros = True

    def __init__(self, node_name: str = "web_viewer") -> None:
        import rclpy  # imported here so sim mode never needs ROS installed
        from rclpy.node import Node
        from std_msgs.msg import String

        self._rclpy = rclpy
        self._String = String
        self._lock = threading.RLock()
        self._subscriptions: Dict[str, List[Subscriber]] = {}
        self._publishers: Dict[str, object] = {}
        # Strong references to the rclpy objects we create. This is not
        # housekeeping: create_subscription() returns an object that rclpy does
        # NOT keep alive for you, so discarding the return value lets Python
        # garbage-collect it, which tears down the DDS subscription while
        # leaving the node itself in the graph. The symptom is maddening --
        # `ros2 topic hz` shows a healthy 5 Hz, the picker receives everything,
        # `ros2 node list` shows the viewer node, and the viewer sees nothing --
        # and it cost a CI cycle to find. See tools/test_transport_lifetime.py.
        self._subscription_objects: List[object] = []
        self._published_count: Dict[str, int] = {}

        rclpy.init(args=None)
        self.node = Node(node_name)
        self._thread: Optional[threading.Thread] = None

    # -- transport interface -------------------------------------------------
    def publish(self, topic: str, payload: str) -> None:
        with self._lock:
            publisher = self._publishers.get(topic)
            if publisher is None:
                publisher = self.node.create_publisher(self._String, topic, 10)
                self._publishers[topic] = publisher
            self._published_count[topic] = self._published_count.get(topic, 0) + 1
        message = self._String()
        message.data = payload
        publisher.publish(message)

    def subscribe(self, topic: str, callback: Subscriber) -> None:
        from std_msgs.msg import String

        with self._lock:
            if topic not in self._subscriptions:
                self._subscriptions[topic] = []

                def _handler(message, _topic=topic):
                    with self._lock:
                        listeners = list(self._subscriptions.get(_topic, ()))
                    for listener in listeners:
                        listener(message.data)

                subscription = self.node.create_subscription(
                    String, topic, _handler, 10
                )
                # Keep it alive (see the note in __init__).
                self._subscription_objects.append(subscription)
            self._subscriptions[topic].append(callback)

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(
                target=self._spin, name="rclpy-spin", daemon=True
            )
            self._thread.start()

    def _spin(self) -> None:
        try:
            self._rclpy.spin(self.node)
        except Exception:  # pragma: no cover - shutdown races only
            pass

    def stop(self) -> None:
        try:
            self.node.destroy_node()
        finally:
            if self._rclpy.ok():
                self._rclpy.shutdown()

    def graph(self) -> dict:
        """Return the real ROS 2 graph as reported by rclpy."""
        node_names = [name for name in self.node.get_node_names() if name]
        topic_pairs = self.node.get_topic_names_and_types()
        nodes = []
        for name in node_names:
            nodes.append({"name": name, "role": "node", "state": "discovered"})
        topics = [
            {
                "name": f"/{name.lstrip('/')}",
                "type": types[0] if types else "unknown",
                "published": self._published_count.get(name, 0),
            }
            for name, types in sorted(topic_pairs)
        ]
        return {
            "is_real": True,
            "nodes": nodes,
            "topics": topics,
            "note": "Live rclpy graph introspection.",
        }


def ros_available() -> bool:
    """Return True when this interpreter can actually import rclpy.

    Deliberately imports rather than checking ``find_spec``: a spec can exist
    while the import still fails (rclpy links native libraries, and a partial
    install is common), and reporting "available" in that case would make the
    viewer fail confusingly later. Importing is also what makes this check
    stubbable in tests -- see tools/test_transport_lifetime.py.
    """
    import importlib

    try:
        importlib.import_module("rclpy")
    except Exception:
        return False
    return True


def build_transport(mode: str):
    """Return a transport for ``mode`` ('sim' or 'ros2'), or raise ValueError."""
    if mode == "sim":
        return SimTransport()
    if mode == "ros2":
        if not ros_available():
            raise ValueError(
                "ROS 2 mode requested but rclpy is not importable. "
                "Source your ROS 2 installation first, e.g. "
                "'source /opt/ros/jazzy/setup.bash', then retry. "
                "Refusing to silently fall back to simulation."
            )
        return RosTransport()
    raise ValueError(f"unknown transport mode: {mode!r} (expected 'sim' or 'ros2')")
