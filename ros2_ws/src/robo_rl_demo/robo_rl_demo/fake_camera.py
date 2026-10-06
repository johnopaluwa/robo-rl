"""Publish synthetic detections; this node does not connect to a real camera.

Thin ROS 2 wrapper: the behaviour lives in :mod:`robo_rl_demo.pipeline`, which is
also what the web viewer in ``web/`` drives. See ``docs/VERIFICATION.md``.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from robo_rl_demo.pipeline import PICK_TOPIC, CameraSource, format_publication


class FakeCameraNode(Node):
    def __init__(self) -> None:
        super().__init__("fake_camera")
        self.declare_parameter("publish_rate_hz", 1.0)
        self.declare_parameter("random_seed", -1)
        self.declare_parameter("topic", PICK_TOPIC)

        seed = int(self.get_parameter("random_seed").value)
        self._source = CameraSource(
            self._publish_payload,
            rate_hz=float(self.get_parameter("publish_rate_hz").value),
            seed=None if seed < 0 else seed,
            topic=str(self.get_parameter("topic").value),
        )
        self._publisher = self.create_publisher(String, self._source.topic, 10)
        self._timer = self.create_timer(self._source.period_s, self._publish_detection)
        self.get_logger().info(
            f"Publishing synthetic detections on '{self._source.topic}' "
            f"at {self._source.rate_hz:g} Hz"
        )

    def _publish_payload(self, topic: str, payload: str) -> None:
        message = String()
        message.data = payload
        self._publisher.publish(message)

    def _publish_detection(self) -> None:
        detection = self._source.tick()
        self.get_logger().info(format_publication(detection))


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
