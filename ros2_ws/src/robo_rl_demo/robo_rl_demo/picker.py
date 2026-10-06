"""Log a safe, illustrative response to each synthetic detection."""

import math

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from robo_rl_demo.detection import (
    DEFAULT_MIN_CONFIDENCE,
    Detection,
    should_attempt_pick,
)


class PickerNode(Node):
    def __init__(self) -> None:
        super().__init__("picker")
        self.declare_parameter("min_confidence", DEFAULT_MIN_CONFIDENCE)
        self.declare_parameter("topic", "detected_object")

        self._min_confidence = float(self.get_parameter("min_confidence").value)
        if not math.isfinite(self._min_confidence) or not (
            0.0 <= self._min_confidence <= 1.0
        ):
            raise ValueError("min_confidence must be between 0 and 1")

        topic = str(self.get_parameter("topic").value).strip()
        if not topic:
            raise ValueError("topic must not be empty")

        self._subscription = self.create_subscription(
            String, topic, self._on_detection, 10
        )
        self.get_logger().info(
            f"Listening on '{topic}'; minimum confidence is {self._min_confidence:.2f}"
        )

    def _on_detection(self, message: String) -> None:
        try:
            detection = Detection.from_json(message.data)
        except ValueError as error:
            self.get_logger().warning(f"Ignoring malformed detection: {error}")
            return

        if should_attempt_pick(detection, self._min_confidence):
            self.get_logger().info(
                f"Would pick #{detection.detection_id} ({detection.label}) at "
                f"({detection.x:.3f}, {detection.y:.3f}) m"
            )
        else:
            self.get_logger().info(
                f"Skipping #{detection.detection_id} ({detection.label}): "
                f"confidence {detection.confidence:.2f} is below "
                f"{self._min_confidence:.2f}"
            )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = PickerNode()
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
