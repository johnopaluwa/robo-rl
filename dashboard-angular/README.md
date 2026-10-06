# dashboard-angular/

Your unfair advantage. The fleet/control dashboard a non-technical business
owner or shift manager actually uses (Phase 4 of the roadmap).

MVP scope:
- Live camera feed from the robot
- Model confidence / status indicator
- Three big buttons: START, STOP, CALL SUPPORT
- An "advanced" view for you: intervention log, success/failure counts, latency

Data gets to the browser via `rosbridge_suite` (ROS 2 <-> WebSocket bridge) —
treat each ROS 2 topic like an RxJS Observable you're already used to
subscribing to.

Nothing here yet — scaffold with `ng new dashboard-angular` once Phase 3
hardware is far enough along to have real data to display.
