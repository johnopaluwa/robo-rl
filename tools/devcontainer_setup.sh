#!/usr/bin/env bash
#
# One-time setup for a Codespaces / devcontainer session, then the real proof.
#
# Run automatically by .devcontainer/devcontainer.json. Idempotent: safe to
# re-run by hand any time.
#
#   bash tools/devcontainer_setup.sh

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; BOLD=$'\033[1m'; RESET=$'\033[0m'

echo "${BOLD}robo-rl devcontainer setup${RESET}"

# --- 1. tools the ROS base image may not ship -------------------------------
MISSING=()
command -v git >/dev/null 2>&1 || MISSING+=(git)
command -v colcon >/dev/null 2>&1 || MISSING+=(python3-colcon-common-extensions)
command -v curl >/dev/null 2>&1 || MISSING+=(curl)

if [ "${#MISSING[@]}" -gt 0 ]; then
  echo "installing: ${MISSING[*]}"
  export DEBIAN_FRONTEND=noninteractive
  if apt-get update -qq && apt-get install -y -qq "${MISSING[@]}" >/dev/null; then
    echo "  ok"
  else
    echo "${RED}could not install ${MISSING[*]}${RESET} -- check network access in this environment."
  fi
fi

# --- 2. ROS 2 environment ---------------------------------------------------
DISTRO="${ROS_DISTRO:-jazzy}"
if [ -f "/opt/ros/$DISTRO/setup.bash" ]; then
  # shellcheck disable=SC1090
  source "/opt/ros/$DISTRO/setup.bash"
  echo "ROS 2 ${GREEN}$DISTRO${RESET} available (rclpy: $(python3 -c 'import rclpy; print(rclpy.__name__)' 2>/dev/null || echo missing))"
else
  echo "${YELLOW}warning${RESET}: /opt/ros/$DISTRO/setup.bash not found; the ROS 2 checks will be skipped."
fi

# --- 3. build the workspace -------------------------------------------------
if [ -f "/opt/ros/$DISTRO/setup.bash" ]; then
  echo "building robo_rl_demo ..."
  ( cd ros2_ws && colcon build --symlink-install --packages-select robo_rl_demo ) \
    >artifacts_setup.log 2>&1 \
    || { echo "${RED}colcon build failed${RESET}; see artifacts_setup.log"; tail -20 artifacts_setup.log; }
  rm -f artifacts_setup.log
fi

# --- 4. prove it, immediately ----------------------------------------------
echo
echo "${BOLD}running the verification suite -- this is the point of the container${RESET}"
echo
if [ -f "/opt/ros/$DISTRO/setup.bash" ]; then
  ./tools/verify.sh --ros2 && ROS2_OK=1 || ROS2_OK=0
else
  ./tools/verify.sh && ROS2_OK=0
fi

echo
if [ "${ROS2_OK:-0}" = "1" ]; then
  echo "${GREEN}ROS 2 is verified in this container.${RESET}"
else
  echo "${YELLOW}ROS 2 was not verified here${RESET} -- read the table above; it says which row failed."
fi
echo
echo "Next, see it in the browser (Codespaces forwards port 8000 automatically):"
echo
echo "  ${BOLD}# terminal 1: the real nodes${RESET}"
echo "  source /opt/ros/$DISTRO/setup.bash && source ros2_ws/install/setup.bash"
echo "  ros2 run robo_rl_demo fake_camera --ros-args -p publish_rate_hz:=5.0"
echo
echo "  ${BOLD}# terminal 2: the viewer against real DDS${RESET}"
echo "  source /opt/ros/$DISTRO/setup.bash && source ros2_ws/install/setup.bash"
echo "  python3 web/server.py --mode ros2 --port 8000"
echo
echo "The badge will read ${GREEN}ROS 2 / DDS LIVE${RESET}, and the log lines are real DDS traffic."
