# ROS 2 workspace

This workspace now contains the first Phase 1 plumbing exercise: a synthetic
camera publisher and a picker subscriber. The example uses `std_msgs/String`
with a small JSON detection payload, so it needs no custom ROS interface
package. The picker only logs what it *would* do; there is no robot driver,
real camera, or motion command here. The item labels are placeholders, not a
chosen customer niche.

## Prerequisites

- A sourced ROS 2 installation (Humble or Jazzy)
- `colcon` and the ROS 2 Python package dependencies (`rclpy`, `std_msgs`,
  `launch`, and `launch_ros`)

From a terminal with the ROS 2 environment available:

```bash
# Source the distro installed on your machine, for example:
source /opt/ros/jazzy/setup.bash

cd ros2_ws
colcon build --symlink-install --packages-select robo_rl_demo
source install/setup.bash
ros2 launch robo_rl_demo demo.launch.py
```

The camera node publishes a synthetic observation once per second to
`detected_object`. The picker logs either `Would pick ...` or `Skipping ...`
depending on the confidence threshold (default `0.65`). Stop the launch with
Ctrl-C. The nodes can also be run separately:

```bash
ros2 run robo_rl_demo fake_camera
ros2 run robo_rl_demo picker
```

Useful parameter overrides:

```bash
ros2 run robo_rl_demo fake_camera --ros-args -p publish_rate_hz:=2.0 -p random_seed:=42
ros2 run robo_rl_demo picker --ros-args -p min_confidence:=0.8
```

Both nodes have a `topic` parameter; set it to the same topic on both if you
change the default.

## Tests without ROS 2

The message validation and decision logic use only the Python standard
library, so they can be tested in a plain Python 3.11 environment from the
repository root:

```bash
PYTHONPATH=ros2_ws/src/robo_rl_demo \
  python3 -m unittest discover -s ros2_ws/src/robo_rl_demo/test -v
```

The Arena development container has Python 3.11 but does not currently have
`rclpy`, `ros2`, or `colcon`. The standard-library tests can run here; the
package build and live publisher/subscriber check still need to be run in a
ROS 2 environment before the corresponding milestone is marked complete.
