"""Publish synthetic detections; this node does not connect to a real camera."""

import math
import random

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from robo_rl_demo.detection import make_demo_detection


class FakeCameraNode(Node):
    def __init__(self) -> None:
        super().__init__("fake_camera")
        self.declare_parameter("publish_rate_hz", 1.0)
        self.declare_parameter("random_seed", -1)
        self.declare_parameter("topic", "detected_object")

        rate_hz = float(self.get_parameter("publish_rate_hz").value)
        if not math.isfinite(rate_hz) or rate_hz <= 0.0:
            raise ValueError(
                "publish_rate_hz must be a finite number greater than zero"
            )

        topic = str(self.get_parameter("topic").value).strip()
        if not topic:
            raise ValueError("topic must not be empty")

        seed = int(self.get_parameter("random_seed").value)
        self._rng = random.Random(None if seed < 0 else seed)
        self._next_detection_id = 0
        self._publisher = self.create_publisher(String, topic, 10)
        self._timer = self.create_timer(1.0 / rate_hz, self._publish_detection)
        self.get_logger().info(
            f"Publishing synthetic detections on '{topic}' at {rate_hz:g} Hz"
        )

    def _publish_detection(self) -> None:
        detection = make_demo_detection(self._rng, self._next_detection_id)
        self._next_detection_id += 1

        message = String()
        message.data = detection.to_json()
        self._publisher.publish(message)
        self.get_logger().info(
            f"Published #{detection.detection_id}: {detection.label} "
            f"at ({detection.x:.3f}, {detection.y:.3f}) m, "
            f"confidence={detection.confidence:.2f}"
        )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = FakeCameraNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
