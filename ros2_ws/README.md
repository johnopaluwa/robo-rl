# ROS 2 workspace

This workspace contains the Phase 1 plumbing exercise: a synthetic camera
publisher and a picker subscriber. The example uses `std_msgs/String` with a
small JSON detection payload, so it needs no custom ROS interface package. The
picker only logs what it *would* do; there is no robot driver, real camera, or
motion command here. The item labels are placeholders, not a chosen niche.

## Structure

```
robo_rl_demo/
├── pipeline.py     # THE behaviour: CameraSource, PickerLogic, command schema
├── detection.py    # message schema + validation (ROS-free, fully testable)
├── fake_camera.py  # thin rclpy wrapper around CameraSource
├── picker.py       # thin rclpy wrapper around PickerLogic (+ arm_command)
└── launch/demo.launch.py
```

All decision logic lives in `pipeline.py`, which imports no ROS. The nodes are
wrappers that translate between `rclpy` and that module, and the web viewer in
`web/` drives the *same* module over an in-process transport. That is why the
simulation is meaningful evidence about the logic — and why it still cannot
prove DDS. See [../docs/VERIFICATION.md](../docs/VERIFICATION.md).

## Topics

| topic | type | direction | payload |
| --- | --- | --- | --- |
| `detected_object` | `std_msgs/String` | camera → picker | `{"id":0,"label":"item_a","x":0.1,"y":-0.2,"confidence":0.87}` |
| `arm_command` | `std_msgs/String` | operator → picker | `{"action":"stop"}` / `{"action":"set_min_confidence","value":0.8}` |

Command actions: `start`, `stop`, `call_support`, `set_min_confidence`.
Malformed commands are logged and ignored, never crash the node.

## Verify it for real

```bash
source /opt/ros/jazzy/setup.bash        # Humble or Jazzy
colcon build --symlink-install --packages-select robo_rl_demo
source install/setup.bash
cd .. && ./tools/verify.sh --ros2       # the honest check
```

`tools/ros2_smoke_test.py` runs both nodes plus an observer, asserts messages
cross DDS, asserts every payload satisfies the schema, asserts the picker decided
on what it received, and asserts that STOP/START published on `arm_command`
actually change node behaviour. Only then may the ROS 2 milestone be ticked.

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
change the default. The picker also has `command_topic` and `accept_commands`
(set `accept_commands:=false` to run it as a pure observer).

## Drive it from the browser

With ROS 2 running, start the viewer in ROS 2 mode and use the real buttons:

```bash
python3 web/server.py --mode ros2
```

It subscribes to the live `detected_object` topic and publishes your button
presses to `arm_command`, which this node obeys. In this mode the UI badge reads
`ROS 2 / DDS LIVE`; in simulation it reads `SIMULATION`, and it never pretends
otherwise.

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
