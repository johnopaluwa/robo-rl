#!/usr/bin/env bash
#
# End-to-end check: real ROS 2 -> web viewer -> browser-facing WebSocket.
#
# This is the "can I see the real thing in the web version?" proof. It starts
# the two real nodes, starts the viewer in --mode ros2, and drives the browser's
# own protocol against it, asserting that the frames carry live DDS data.
#
#   source /opt/ros/jazzy/setup.bash
#   ./tools/ros2_viewer_check.sh
#
# Exit codes: 0 pass, 1 fail, 3 skipped (no ROS 2 available).
#
# NOTE: this script could not be executed in the development container that
# wrote it (no rclpy there). Its first real run is in CI or on your machine --
# which is deliberate: an untested claim should be visible, not hidden.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PORT=${PORT:-8123}
RATE=${RATE:-5.0}
SECONDS_TO_OBSERVE=${SECONDS_TO_OBSERVE:-8}
ARTIFACT_DIR="artifacts/proofs"
mkdir -p "$ARTIFACT_DIR"

GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; RESET=$'\033[0m'

if ! python3 -c "import rclpy" 2>/dev/null; then
  echo "${YELLOW}SKIP${RESET}: rclpy is not importable, so the ROS 2 web path cannot be verified here."
  echo "      source /opt/ros/jazzy/setup.bash   # then re-run"
  exit 3
fi

DISTRO="${ROS_DISTRO:-jazzy}"
if [ ! -f "/opt/ros/$DISTRO/setup.bash" ]; then
  echo "${RED}FAIL${RESET}: /opt/ros/$DISTRO/setup.bash not found. Source your ROS 2 install first."
  exit 1
fi
echo "ROS 2 distro: $DISTRO"

# --- build the workspace if it has not been built --------------------------
if [ ! -d "ros2_ws/install/robo_rl_demo" ]; then
  echo "building robo_rl_demo ..."
  if ! ( cd ros2_ws && colcon build --symlink-install --packages-select robo_rl_demo ) \
       >"$ARTIFACT_DIR/colcon_build.log" 2>&1; then
    echo "${RED}FAIL${RESET}: colcon build failed; see $ARTIFACT_DIR/colcon_build.log"
    tail -20 "$ARTIFACT_DIR/colcon_build.log"
    exit 1
  fi
fi

# shellcheck disable=SC1090
source "/opt/ros/$DISTRO/setup.bash"
# shellcheck disable=SC1091
source "ros2_ws/install/setup.bash"

declare -a PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null; done
  for pid in "${PIDS[@]:-}"; do wait "$pid" 2>/dev/null; done
}
trap cleanup EXIT

# --- real nodes ------------------------------------------------------------
echo "starting fake_camera + picker ..."
ros2 run robo_rl_demo fake_camera --ros-args -p "publish_rate_hz:=$RATE" \
  >"$ARTIFACT_DIR/ros2_fake_camera.log" 2>&1 &
PIDS+=($!)
ros2 run robo_rl_demo picker >"$ARTIFACT_DIR/ros2_picker.log" 2>&1 &
PIDS+=($!)

# The picker's own log is the node-level evidence; wait for the topic to exist.
TOPIC_READY=0
for _ in $(seq 1 40); do
  if ros2 topic list 2>/dev/null | grep -q "^/detected_object$"; then
    TOPIC_READY=1
    break
  fi
  sleep 0.5
done
if [ "$TOPIC_READY" != "1" ]; then
  echo "${RED}FAIL${RESET}: /detected_object never appeared. Node logs:"
  tail -20 "$ARTIFACT_DIR/ros2_fake_camera.log"
  exit 1
fi
echo "  /detected_object is up"

# --- viewer in real ROS 2 mode --------------------------------------------
echo "starting the viewer in --mode ros2 ..."
python3 web/server.py --mode ros2 --port "$PORT" --rate "$RATE" --quiet \
  >"$ARTIFACT_DIR/ros2_viewer.log" 2>&1 &
PIDS+=($!)

VIEWER_READY=0
for _ in $(seq 1 40); do
  if curl -sS --max-time 2 "http://127.0.0.1:$PORT/api/health" \
       | grep -q '"is_real_ros":true'; then
    VIEWER_READY=1
    break
  fi
  sleep 0.5
done
if [ "$VIEWER_READY" != "1" ]; then
  echo "${RED}FAIL${RESET}: viewer did not report real ROS 2 mode. Its log:"
  tail -20 "$ARTIFACT_DIR/ros2_viewer.log"
  exit 1
fi
echo "  viewer reports is_real_ros=true"

# --- drive the browser's own protocol -------------------------------------
echo "probing the browser-facing WebSocket (expecting live DDS data) ..."
if python3 tools/ws_probe.py --port "$PORT" --seconds "$SECONDS_TO_OBSERVE" \
     --expect-ros2 --json "$ARTIFACT_DIR/ros2_viewer_probe.json"; then
  echo
  echo "${GREEN}PASS${RESET}: the browser saw live ROS 2 data end to end."
  echo "      artifact: $ARTIFACT_DIR/ros2_viewer_probe.json"
  echo "      node log: $ARTIFACT_DIR/ros2_picker.log"
  exit 0
fi
echo
echo "${RED}FAIL${RESET}: the browser-facing path did not carry live ROS 2 data."
echo "      viewer log: $ARTIFACT_DIR/ros2_viewer.log"
echo "      picker log: $ARTIFACT_DIR/ros2_picker.log"
exit 1
