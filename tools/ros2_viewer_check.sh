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
# Diagnostics: on any failure this emits a GitHub annotation (::error::) with
# the tail of the relevant log, and writes everything to
# artifacts/proofs/ros2_viewer_diagnostics.txt. That exists because CI job logs
# are not always reachable from every environment, while annotations are.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# All participants in this check are on one machine. Loopback-only discovery
# avoids the classic cloud/CI failure where multicast discovery across the VM's
# network interface never completes, so the nodes exist but never see each other.
# Override by exporting ROS_LOCALHOST_ONLY=0 if you deliberately need the LAN.
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-1}"

PORT=${PORT:-8123}
RATE=${RATE:-5.0}
SECONDS_TO_OBSERVE=${SECONDS_TO_OBSERVE:-10}
READY_TIMEOUT=${READY_TIMEOUT:-45}
ARTIFACT_DIR="artifacts/proofs"
mkdir -p "$ARTIFACT_DIR"
DIAG="$ARTIFACT_DIR/ros2_viewer_diagnostics.txt"

GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; RESET=$'\033[0m'

# One place for diagnostics, so failures are readable from CI annotations too.
: >"$DIAG"
note() { echo "$*" | tee -a "$DIAG"; }
fail() {
  note "FAIL: $*"
  # GitHub annotation: newlines must be percent-escaped to stay on one line.
  local escaped
  escaped=$(printf '%s' "$*" | sed ':a;N;$!ba;s/\n/%0A/g' | cut -c1-4000)
  # Anchored to a file: unanchored annotations are not always returned by the
  # check-runs annotations API, and that API is the only reliable way to read a
  # failure from an environment that cannot reach the job-log storage.
  echo "::error file=tools/ros2_viewer_check.sh,line=1::${escaped}"
  exit 1
}

if ! python3 -c "import rclpy" 2>/dev/null; then
  echo "${YELLOW}SKIP${RESET}: rclpy is not importable, so the ROS 2 web path cannot be verified here."
  echo "      source /opt/ros/jazzy/setup.bash   # then re-run"
  exit 3
fi

DISTRO="${ROS_DISTRO:-jazzy}"
if [ ! -f "/opt/ros/$DISTRO/setup.bash" ]; then
  fail "/opt/ros/$DISTRO/setup.bash not found. Source your ROS 2 install first."
fi
note "ROS 2 distro: $DISTRO"
note "python: $(python3 --version 2>&1), rclpy: $(python3 -c 'import rclpy, pathlib; print(pathlib.Path(rclpy.__file__).parent)' 2>&1)"

# --- build the workspace if needed -----------------------------------------
if [ ! -d "ros2_ws/install/robo_rl_demo" ]; then
  note "building robo_rl_demo ..."
  if ! ( cd ros2_ws && colcon build --symlink-install --packages-select robo_rl_demo ) \
       >"$ARTIFACT_DIR/colcon_build.log" 2>&1; then
    fail "colcon build failed:
$(tail -25 "$ARTIFACT_DIR/colcon_build.log")"
  fi
fi

# ROS 2's setup scripts and colcon's generated overlays are NOT written to be
# compatible with `set -u`, and referencing one of their unset variables makes
# bash abort the whole script with status 1 and no message of its own. That is
# exactly how this script failed its first two CI runs: it printed the two notes
# above, then died silently at these two lines. Relax nounset just for sourcing.
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
note "executables: $(ros2 pkg executables robo_rl_demo 2>&1 | tr '\n' ' ')"

declare -a PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null; done
  for pid in "${PIDS[@]:-}"; do wait "$pid" 2>/dev/null; done
}

# Record any exit that did not come from an explicit FAIL (exit 3 is the
# deliberate "no ROS 2 here" skip). A silent abort is otherwise invisible in the
# diagnostics file -- which is how the first two failures presented.
on_exit() {
  local rc=$?
  cleanup
  if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
    note "ABORTED with status $rc before reporting a FAIL (check this step's stderr in the job log)"
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

# NB: capture output into a variable rather than piping into `grep -q`. Under
# `set -o pipefail`, grep -q exiting early can SIGPIPE the producer and turn a
# successful match into a failed pipeline -- a race that shows up only on faster
# or slower machines. This cost a red CI run to find.
TOPIC_READY=0
for _ in $(seq 1 "$((READY_TIMEOUT * 2))"); do
  TOPIC_LIST="$(ros2 topic list 2>/dev/null || true)"
  case "$TOPIC_LIST" in
    *"/detected_object"*) TOPIC_READY=1; break ;;
  esac
  sleep 0.5
done
if [ "$TOPIC_READY" != "1" ]; then
  fail "/detected_object never appeared within ${READY_TIMEOUT}s.
topics seen: $(echo "$TOPIC_LIST" | tr '\n' ' ')
fake_camera log:
$(tail -20 "$ARTIFACT_DIR/ros2_fake_camera.log")"
fi
note "  /detected_object is up; topics: $(echo "$TOPIC_LIST" | tr '\n' ' ')"

# --- viewer in real ROS 2 mode --------------------------------------------
note "starting the viewer in --mode ros2 on port $PORT ..."
python3 web/server.py --mode ros2 --port "$PORT" --rate "$RATE" --quiet \
  >"$ARTIFACT_DIR/ros2_viewer.log" 2>&1 &
PIDS+=($!)

HEALTH=""
VIEWER_READY=0
for _ in $(seq 1 "$((READY_TIMEOUT * 2))"); do
  HEALTH="$(curl -sS --max-time 2 "http://127.0.0.1:$PORT/api/health" 2>/dev/null || true)"
  case "$HEALTH" in
    *'"is_real_ros":true'*) VIEWER_READY=1; break ;;
  esac
  if ! kill -0 "${PIDS[-1]}" 2>/dev/null; then
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
TOPIC_INFO="$(ros2 topic info /detected_object 2>&1 | tr '\n' '; ' || true)"
TOPIC_HZ="$(timeout 6 ros2 topic hz /detected_object --window 20 2>&1 | head -3 | tr '\n' '; ' || true)"
NODE_LIST="$(ros2 node list 2>&1 | tr '\n' ' ' || true)"
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
