# web/ — live viewer and the prototype of the Phase 4 dashboard

A dependency-free web viewer for the pipeline: it shows detections arriving,
the picker's decisions, counters, an event log, and the ROS 2 graph — and lets
you drive it with START / STOP / CALL SUPPORT.

It exists for one reason: **every milestone needs something you can look at, and
look at again.** See [`docs/VERIFICATION.md`](../docs/VERIFICATION.md) for how
this fits into the wider verification system.

```bash
python3 web/server.py                                   # simulation: runs anywhere
source /opt/ros/jazzy/setup.bash
python3 web/server.py --mode ros2                       # live DDS (needs ROS 2)
```

Then open <http://localhost:8000>.

## Two modes, one code path

| | `--mode sim` (default) | `--mode ros2` |
| --- | --- | --- |
| Transport | in-process broker | rclpy / DDS |
| Behaviour code | `robo_rl_demo/pipeline.py` | **the same** `pipeline.py` |
| Needs ROS 2 | no | yes — refuses to start without it |
| Proves | logic, wiring, protocol | that plus real pub/sub and command delivery |
| Label in the UI | `SIMULATION` (amber) | `ROS 2 / DDS LIVE` (green) |

`--mode ros2` exits with an error if `rclpy` is missing. It will not quietly
fall back to simulation, because a screenshot that *looks* like ROS 2 but is not
would be worse than no screenshot.

In ROS 2 mode, also run the real nodes so there is traffic to see:

```bash
cd ros2_ws && colcon build --symlink-install --packages-select robo_rl_demo
source install/setup.bash && ros2 launch robo_rl_demo demo.launch.py
```

The viewer subscribes to the live `detected_object` topic, and publishes your
button presses to `arm_command`, which the real picker node obeys.

## What you are looking at

- **The cell** — object position from the detection message, the arm moving
  through approach → carry → settle, four destination bins. Low-confidence items
  land in `NEEDS HUMAN`: that is the Wizard-of-Oz teleop fallback from
  `BUSINESS_PLAN.md`, made visible and countable.
- **Operator controls** — the three buttons a customer sees. Everything else is
  under *Advanced*, which is your view, not theirs.
- **Advanced** — the `min_confidence` slider is the exact parameter the ROS 2
  picker node takes (`-p min_confidence:=0.8`). Lowering it attempts more picks
  and causes more failed grasps; raising it sends more work to a human. That
  trade-off is the whole job.
- **Counters / rates** — `grasp success` and `needs human` are the two numbers a
  pilot lives or dies on: the intervention rate must trend down.
- **Pipeline log** — produced by the shared pipeline module, so the wording is
  byte-identical to what a ROS 2 node logs.
- **ROS 2 graph** — in sim mode this is explicitly labelled *modelled*; in ros2
  mode it is live `rclpy` introspection.

## How the browser gets data

A WebSocket at `/ws`, with an automatic fallback to polling `GET /api/state` at
5 Hz if the upgrade is blocked (some proxies and preview panes block it). Both
paths render the identical snapshot, so the numbers can never disagree.

| endpoint | purpose |
| --- | --- |
| `GET /` | the viewer |
| `GET /api/health` | mode, transport, uptime, connected clients |
| `GET /api/state` | full snapshot (also the polling fallback) |
| `POST /api/command` | `{"action": "start"\|"stop"\|"call_support"\|"set_min_confidence", "value": 0.8}` |
| `POST /api/sim_config` | sim only: `{"rate_hz": 2, "auto_pause_on_review": true, "reset": true}` |
| `POST /api/resolve_review` | resume after a review pause |
| `WS /ws` | `{"op":"subscribe"}`, `{"op":"publish","msg":{...}}` |

Command JSON is identical to what travels over ROS 2 on `arm_command`, and it is
parsed by the same `parse_command` — so the button you click here is the button
the robot eventually obeys.

## Why vanilla JS instead of Angular

This container has no npm registry access at runtime and `node_modules/` is not
persisted, so a build-step app would be un-runnable for the next person who
clones the repo. More importantly, **Phase 4 is when the Angular dashboard
happens** — building it now would be the classic mistake of polishing the UI
before there is a customer.

So this file is the *specification*: same snapshot shape, same command schema,
same three buttons. Port it to Angular with `WebSocketSubject` (your existing
RxJS mental model maps 1:1 onto ROS 2 topics) when Phase 4 arrives, and keep
`tools/ws_probe.py` working against the replacement — it is transport-level, not
framework-level.

## Files

```
web/
├── server.py           # HTTP + WebSocket server, stdlib only
├── transports.py       # SimTransport (in-process) / RosTransport (rclpy)
├── pipeline_runner.py  # world model, counters, log, snapshot for the browser
└── static/
    ├── index.html
    ├── app.js          # render(snapshot), commands, ws + polling fallback
    └── styles.css
```

Nothing here is a substitute for `rosbridge_suite` in Phase 4 — it is a smaller,
dependency-free stand-in for the same idea (ROS topics → WebSocket → browser),
and the honest way to see your pipeline work today.
