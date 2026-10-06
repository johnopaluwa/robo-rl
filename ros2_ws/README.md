# ros2_ws/

The ROS 2 workspace: drivers for the physical arm/camera, the perception
pipeline, and the node that runs your trained policy on real hardware
(Phase 1 and 3 of the roadmap).

Suggested structure once you have packages:
```
ros2_ws/
└── src/
    ├── <arm>_driver/        # wraps the arm's SDK as a ROS 2 node
    ├── perception/          # camera -> detection/segmentation -> pose
    ├── policy_runner/       # loads the trained policy, publishes actions
    └── teleop_bridge/       # manual override / "Wizard of Oz" fallback
```
Nothing here yet — start with the official ROS 2 beginner tutorials
(docs.ros.org) to build your first toy publisher/subscriber pair.
