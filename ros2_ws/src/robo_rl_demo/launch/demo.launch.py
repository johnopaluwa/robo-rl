"""Launch the fake camera publisher and its picker subscriber together."""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            Node(
                package="robo_rl_demo",
                executable="fake_camera",
                name="fake_camera",
                output="screen",
            ),
            Node(
                package="robo_rl_demo",
                executable="picker",
                name="picker",
                output="screen",
            ),
        ]
    )
