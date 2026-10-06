"""Decide what to do with each synthetic detection, and accept operator commands.

Thin ROS 2 wrapper: parsing, thresholds and decision wording all live in
:mod:`robo_rl_demo.pipeline`, which the web viewer drives too. The command
subscription is what lets the browser's START / STOP / CALL SUPPORT buttons drive
this real node once ROS 2 is running -- see ``docs/VERIFICATION.md``.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from robo_rl_demo.detection import DEFAULT_MIN_CONFIDENCE
from robo_rl_demo.pipeline import (
    COMMAND_TOPIC,
    PICK_TOPIC,
    OperatorCommand,
    PickResult,
    PickerLogic,
    parse_command,
)


class PickerNode(Node):
    def __init__(self) -> None:
        super().__init__("picker")
        self.declare_parameter("min_confidence", DEFAULT_MIN_CONFIDENCE)
        self.declare_parameter("topic", PICK_TOPIC)
        self.declare_parameter("command_topic", COMMAND_TOPIC)
        self.declare_parameter("accept_commands", True)

        self._accept_commands = bool(self.get_parameter("accept_commands").value)
        self._enabled = True
        self._logic = PickerLogic(
            min_confidence=float(self.get_parameter("min_confidence").value),
            on_result=self._log_result,
        )

        command_topic = str(self.get_parameter("command_topic").value).strip()
        subscription = self.create_subscription(
            String,
            str(self.get_parameter("topic").value),
            self._on_detection,
            10,
        )
        self._command_subscription = None
        if self._accept_commands:
            self._command_subscription = self.create_subscription(
                String, command_topic, self._on_command, 10
            )

        self._subscription = subscription
        self.get_logger().info(
            f"Listening on '{str(self.get_parameter('topic').value)}'; "
            f"minimum confidence is {self._logic.min_confidence:.2f}"
        )
        if self._accept_commands:
            self.get_logger().info(f"Accepting operator commands on '{command_topic}'")

    @property
    def stats(self) -> dict:
        """Read-only snapshot of this node's decisions, for tests and the dashboard."""
        return {
            "attempted": self._logic.count_attempted,
            "skipped": self._logic.count_skipped,
            "malformed": self._logic.count_malformed,
            "min_confidence": self._logic.min_confidence,
            "decisions": (
                self._logic.count_attempted
                + self._logic.count_skipped
                + self._logic.count_malformed
            ),
            "enabled": self._enabled,
            "accept_commands": self._accept_commands,
        }

    def _log_result(self, result: PickResult) -> None:
        if result.malformed:
            self.get_logger().warning(result.message)
        else:
            self.get_logger().info(result.message)

    def _on_detection(self, message: String) -> None:
        if not self._enabled:
            self.get_logger().info(
                f"Operator stop is active; ignoring {message.data!r}"
            )
            return
        self._logic.handle_payload(message.data)

    def _on_command(self, message: String) -> None:
        try:
            command = parse_command(message.data)
        except ValueError as error:
            self.get_logger().warning(f"Ignoring malformed command: {error}")
            return
        self._apply_command(command)

    def _apply_command(self, command: OperatorCommand) -> None:
        if command.action == "start":
            self._enabled = True
            self.get_logger().info("Operator start: picking enabled")
        elif command.action == "stop":
            self._enabled = False
            self.get_logger().info("Operator stop: picking disabled")
        elif command.action == "set_min_confidence":
            threshold = self._logic.set_min_confidence(command.value)
            self.get_logger().info(f"Minimum confidence set to {threshold:.2f}")
        elif command.action == "call_support":
            self.get_logger().info("Support requested by operator (teleop fallback)")


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
