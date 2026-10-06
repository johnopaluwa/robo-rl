#!/usr/bin/env bash
#
# End-to-end check: real ROS 2 -> web viewer -> browser-facing WebSocket.
#
# This is the "can I see the real thing in the web version?" proof. It starts
# the two real nodes, starts the viewer in --mode ros2, and drives the browser's
# own protocol against it, asserting the frames carry live DDS data.
#
#   source /opt/ros/jazzy/setup.bash
#   ./tools/ros2_viewer_check.sh
#
# Exit codes: 0 pass, 1 fail, 3 skipped (no ROS 2 available).
#
# Two hard-won rules are baked into this file, because a check that hangs or
# fails silently is worse than no check:
#
#   1. EVERY external call is wrapped in `timeout`. The `ros2` CLI talks to a
#      discovery daemon and can block indefinitely if that daemon is unhealthy;
#      unwrapped, this script hung a CI runner for 12+ minutes with no output.
#   2. Progress and failure details are appended to a diagnostics file as the
#      script goes, not at the end, so a failure -- or a timeout that kills the
#      script outright -- still leaves behind an explanation.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# All participants are on one machine here. Loopback-only discovery avoids the
# classic cloud/CI failure where multicast discovery across the VM's network
# interface never completes, so nodes exist but never see each other.
# Export ROS_LOCALHOST_ONLY=0 to override if you deliberately need the LAN.
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-1}"

PORT=${PORT:-8123}
RATE=${RATE:-5.0}
SECONDS_TO_OBSERVE=${SECONDS_TO_OBSERVE:-10}
READY_TIMEOUT=${READY_TIMEOUT:-45}
CLI_TIMEOUT=${CLI_TIMEOUT:-15}
ARTIFACT_DIR="artifacts/proofs"
mkdir -p "$ARTIFACT_DIR"
DIAG="$ARTIFACT_DIR/ros2_viewer_diagnostics.txt"

GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; RESET=$'\033[0m'

: >"$DIAG"
note() { echo "$*" | tee -a "$DIAG"; }

fail() {
  note "FAIL: $*"
  local escaped
  escaped=$(printf '%s' "$*" | sed ':a;N;$!ba;s/\n/%0A/g' | cut -c1-4000)
  # Anchored to a file: annotations without a file are not always returned by
  # the check-runs annotations API, which is the only failure channel reachable
  # from environments that cannot read job logs.
  echo "::error file=tools/ros2_viewer_check.sh,line=1::${escaped}"
  exit 1
}

# Every ros2 CLI call goes through here. `|| true` keeps the output usable even
# when timeout kills the call, so callers always get text to report.
ros2_cli() {
  local limit="$1"; shift
  timeout "$limit" ros2 "$@" 2>&1 || true
}

if ! python3 -c "import rclpy" 2>/dev/null; then
  echo "${YELLOW}SKIP${RESET}: rclpy is not importable, so the ROS 2 web path cannot be verified here."
  echo "      source /opt/ros/jazzy/setup.bash   # then re-run"
  exit 3
fi

DISTRO="${ROS_DISTRO:-jazzy}"
[ -f "/opt/ros/$DISTRO/setup.bash" ] \
  || fail "/opt/ros/$DISTRO/setup.bash not found. Source your ROS 2 install first."
note "ROS 2 distro: $DISTRO"
note "python: $(python3 --version 2>&1), rclpy: $(python3 -c 'import rclpy, pathlib; print(pathlib.Path(rclpy.__file__).parent)' 2>&1)"

if [ ! -d "ros2_ws/install/robo_rl_demo" ]; then
  note "building robo_rl_demo ..."
  if ! ( cd ros2_ws && colcon build --symlink-install --packages-select robo_rl_demo ) \
       >"$ARTIFACT_DIR/colcon_build.log" 2>&1; then
    fail "colcon build failed:
$(tail -25 "$ARTIFACT_DIR/colcon_build.log")"
  fi
fi

# ROS 2's setup scripts and colcon's generated overlays are NOT written to be
# compatible with `set -u`: referencing one of their unset variables makes bash
# abort the whole script with status 1 and a stderr message only. That is how
# this script failed its first two CI runs, silently. Relax nounset just here.
set +u
note "sourcing /opt/ros/$DISTRO/setup.bash ..."
# shellcheck disable=SC1090
source "/opt/ros/$DISTRO/setup.bash"
note "  ros2 CLI: $(command -v ros2 || echo 'NOT FOUND on PATH')"
if [ ! -f "ros2_ws/install/setup.bash" ]; then
  fail "ros2_ws/install/setup.bash not found. Build the workspace first:
  ( cd ros2_ws && colcon build --symlink-install --packages-select robo_rl_demo )"
fi
# shellcheck disable=SC1091
source "ros2_ws/install/setup.bash"
note "  workspace overlay sourced"
set -u

note "package executables: $(ros2_cli "$CLI_TIMEOUT" pkg executables robo_rl_demo | tr '\n' ' ')"

# A daemon left over from a previous step (verify.sh --ros2 starts nodes too) is
# a plausible cause of a CLI call blocking. Stop it and let it restart clean.
note "resetting the ros2 daemon: $(ros2_cli "$CLI_TIMEOUT" daemon stop | tr '\n' ' ')"

declare -a PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null; done
  for pid in "${PIDS[@]:-}"; do wait "$pid" 2>/dev/null; done
}
on_exit() {
  local rc=$?
  cleanup
  if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
    note "ABORTED with status $rc before reporting a FAIL (a timeout may have killed this script; see this step's log)"
  fi
}
trap on_exit EXIT

# --- real nodes ------------------------------------------------------------
note "starting fake_camera + picker ..."
ros2 run robo_rl_demo fake_camera --ros-args -p "publish_rate_hz:=$RATE" \
  >"$ARTIFACT_DIR/ros2_fake_camera.log" 2>&1 &
PIDS+=($!)
ros2 run robo_rl_demo picker >"$ARTIFACT_DIR/ros2_picker.log" 2>&1 &
PIDS+=($!)

note "waiting for /detected_object (up to ${READY_TIMEOUT}s) ..."
TOPIC_READY=0
TOPIC_LIST=""
for _ in $(seq 1 "$((READY_TIMEOUT * 2))"); do
  TOPIC_LIST="$(ros2_cli "$CLI_TIMEOUT" topic list)"
  case "$TOPIC_LIST" in
    *"/detected_object"*) TOPIC_READY=1; break ;;
  esac
  sleep 0.5
done
if [ "$TOPIC_READY" != "1" ]; then
  fail "/detected_object never appeared within ${READY_TIMEOUT}s.
topics seen: $(echo "$TOPIC_LIST" | tr '\n' ' ')
executables: $(ros2_cli "$CLI_TIMEOUT" pkg executables robo_rl_demo | tr '\n' ' ')
fake_camera log:
$(tail -20 "$ARTIFACT_DIR/ros2_fake_camera.log")"
fi
note "  /detected_object is up; topics: $(echo "$TOPIC_LIST" | tr '\n' ' ')"

# --- viewer in real ROS 2 mode --------------------------------------------
note "starting the viewer in --mode ros2 on port $PORT ..."
python3 web/server.py --mode ros2 --port "$PORT" --rate "$RATE" --quiet \
  >"$ARTIFACT_DIR/ros2_viewer.log" 2>&1 &
PIDS+=($!)
VIEWER_PID=$!

HEALTH=""
VIEWER_READY=0
for _ in $(seq 1 "$((READY_TIMEOUT * 2))"); do
  HEALTH="$(curl -sS --max-time 2 "http://127.0.0.1:$PORT/api/health" 2>/dev/null || true)"
  case "$HEALTH" in
    *'"is_real_ros":true'*) VIEWER_READY=1; break ;;
  esac
  if ! kill -0 "$VIEWER_PID" 2>/dev/null; then
    note "viewer process exited early"
    break
  fi
  sleep 0.5
done
if [ "$VIEWER_READY" != "1" ]; then
  fail "the viewer never reported real ROS 2 mode within ${READY_TIMEOUT}s.
last health response: ${HEALTH:-<none>}
viewer log:
$(tail -20 "$ARTIFACT_DIR/ros2_viewer.log")"
fi
note "  viewer health: $HEALTH"

# --- drive the browser's own protocol -------------------------------------
note "probing the browser-facing WebSocket (expecting live DDS data) ..."
if python3 tools/ws_probe.py --port "$PORT" --seconds "$SECONDS_TO_OBSERVE" \
     --expect-ros2 --json "$ARTIFACT_DIR/ros2_viewer_probe.json" 2>&1 | tee -a "$DIAG"; then
  echo
  echo "${GREEN}PASS${RESET}: the browser saw live ROS 2 data end to end."
  note "PASS: browser path carried live DDS data"
  exit 0
fi

# Distinguish "DDS is not delivering" from "our bridge is broken": ask the ROS
# CLI directly, independently of the viewer.
TOPIC_INFO="$(ros2_cli "$CLI_TIMEOUT" topic info /detected_object | tr '\n' '; ')"
TOPIC_HZ="$(timeout 6 ros2 topic hz /detected_object --window 20 2>&1 | head -3 | tr '\n' '; ' || true)"
NODE_LIST="$(ros2_cli "$CLI_TIMEOUT" node list | tr '\n' ' ')"
note "ros2 topic info: $TOPIC_INFO"
note "ros2 topic hz:   $TOPIC_HZ"
note "ros2 node list:  $NODE_LIST"

fail "the browser-facing WebSocket did not carry live ROS 2 data.
ros2 topic info: $TOPIC_INFO
ros2 topic hz (5s): $TOPIC_HZ
ros2 node list: $NODE_LIST
picker log:
$(tail -20 "$ARTIFACT_DIR/ros2_picker.log")
viewer log:
$(tail -20 "$ARTIFACT_DIR/ros2_viewer.log")"
