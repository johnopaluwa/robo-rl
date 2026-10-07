# dashboard-angular/

Your unfair advantage. The fleet/control dashboard a non-technical business
owner or shift manager actually uses (Phase 4 of the roadmap — **built last,
deliberately**: no UI before the robot it monitors actually works).

MVP scope:
- Live camera feed from the robot
- Model confidence / status indicator
- Three big buttons: START, STOP, CALL SUPPORT
- An "advanced" view for you: intervention log, success/failure counts, latency

Data gets to the browser via `rosbridge_suite` (ROS 2 <-> WebSocket bridge) —
treat each ROS 2 topic like an RxJS Observable you're already used to
subscribing to.

Nothing here yet — scaffold with `ng new dashboard-angular` once the Phase 3
robot is functional enough to have real data to display. Until then,
[`web/`](../web/README.md) is the living specification: same snapshot shape,
same command schema, same three buttons.
