#!/usr/bin/env bash
#
# One command that verifies what is actually verifiable in this checkout.
#
#   ./tools/verify.sh            # everything except ROS 2 (skips it, clearly)
#   ./tools/verify.sh --ros2     # also verifies against real ROS 2 (must pass)
#
# Design rule: this script never reports a milestone as verified when the thing
# that proves it did not run. Simulation results are labelled (sim), ROS 2
# results are labelled (ros2), and anything that could not run is NOT VERIFIED.
#
# Exit codes: 0 = nothing failed, 1 = something failed.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PACKAGE_ROOT="ros2_ws/src/robo_rl_demo"
ARTIFACT_DIR="artifacts/proofs"
mkdir -p "$ARTIFACT_DIR"

REQUIRE_ROS2=0
for arg in "$@"; do
  case "$arg" in
    --ros2) REQUIRE_ROS2=1 ;;
    -h|--help)
      sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; RED=$'\033[31m'
YELLOW=$'\033[33m'; CYAN=$'\033[36m'; RESET=$'\033[0m'

declare -a NAMES STATUS TRANSPORT DETAIL
FAILED=0

record() { # name status transport detail
  NAMES+=("$1"); STATUS+=("$2"); TRANSPORT+=("$3"); DETAIL+=("$4")
  if [ "$2" = "FAIL" ]; then FAILED=1; fi
}

step_header() { printf '\n%s==> %s%s\n' "$BOLD" "$1" "$RESET"; }

# ---------------------------------------------------------------- 1. unit tests
step_header "Unit tests (no ROS 2 needed)"
TEST_LOG="$ARTIFACT_DIR/unit_tests.txt"
if PYTHONPATH="$PACKAGE_ROOT" python3 -m unittest discover \
     -s "$PACKAGE_ROOT/test" -v >"$TEST_LOG" 2>&1; then
  COUNT=$(grep -oE 'Ran [0-9]+ tests' "$TEST_LOG" | grep -oE '[0-9]+' | head -1)
  echo "  ${GREEN}PASS${RESET} ${COUNT:-?} tests"
  record "unit tests" PASS "python 3" "${COUNT:-?} tests -> $TEST_LOG"
else
  tail -25 "$TEST_LOG"
  echo "  ${RED}FAIL${RESET} see $TEST_LOG"
  record "unit tests" FAIL "python 3" "see $TEST_LOG"
fi

# ------------------------------------------------------- 2. headless pipeline
step_header "Headless pipeline proof (no ROS 2 needed)"
if python3 tools/proof_pipeline.py --artifact-dir "$ARTIFACT_DIR"; then
  VERDICT=$(python3 -c "import json;print(json.load(open('$ARTIFACT_DIR/pipeline_proof.json'))['verdict'])")
  record "pipeline logic proof" PASS "(sim)" "transport=in-process -> pipeline_proof.json"
else
  record "pipeline logic proof" FAIL "(sim)" "see pipeline_proof.json"
fi

# --------------------------------------------------------- 3. live web viewer
step_header "Live web viewer + WebSocket round-trip (no ROS 2 needed)"
PORT=$(python3 -c "import socket;s=socket.socket();s.bind(('',0));print(s.getsockname()[1]);s.close()")
SERVER_LOG="$ARTIFACT_DIR/viewer_server.log"
python3 web/server.py --mode sim --port "$PORT" --rate 2 --quiet >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" 2>/dev/null; wait "$SERVER_PID" 2>/dev/null; }
trap cleanup EXIT

READY=0
for _ in $(seq 1 40); do
  if curl -sS --max-time 2 "http://127.0.0.1:$PORT/api/health" >"$ARTIFACT_DIR/viewer_health.json" 2>/dev/null; then
    READY=1; break
  fi
  sleep 0.25
done

if [ "$READY" = "1" ]; then
  echo "  server up on port $PORT (pid $SERVER_PID)"
  if python3 tools/ws_probe.py --port "$PORT" --seconds 5 \
       --json "$ARTIFACT_DIR/ws_probe.json"; then
    record "live viewer + ws commands" PASS "(sim)" "handshake, frames, stop/start -> ws_probe.json"
  else
    record "live viewer + ws commands" FAIL "(sim)" "see ws_probe.json"
  fi

  # Guard: the ROS 2 assertion must actually discriminate. A claim-check that
  # passes against a simulation would be worse than no check at all, so prove
  # here that demanding ROS 2 evidence fails when only simulation exists.
  if python3 tools/ws_probe.py --port "$PORT" --seconds 3 --expect-ros2 --quiet >/dev/null 2>&1; then
    echo "  ${RED}FAIL${RESET} --expect-ros2 accepted simulation data; the honesty check is broken"
    record "honesty guard: sim rejected as ROS 2" FAIL "(sim)" "--expect-ros2 passed on a simulation"
  else
    echo "  ${GREEN}PASS${RESET} --expect-ros2 correctly refuses simulation-only evidence"
    record "honesty guard: sim rejected as ROS 2" PASS "(sim)" "--expect-ros2 fails on sim, as it must"
  fi
else
  echo "  ${RED}server did not become ready${RESET}; see $SERVER_LOG"
  record "live viewer + ws commands" FAIL "(sim)" "server never became ready"
fi
cleanup; trap - EXIT

# ------------------------------------------------- 3c. probe regression tests
step_header "Tools tests: probe regression + frontend/backend contract"
PROBE_LOG="$ARTIFACT_DIR/probe_tests.txt"
if python3 -m unittest discover -s tools -p 'test_*.py' -v >"$PROBE_LOG" 2>&1; then
  PROBE_COUNT=$(grep -oE 'Ran [0-9]+ tests' "$PROBE_LOG" | grep -oE '[0-9]+' | head -1)
  echo "  ${GREEN}PASS${RESET} ${PROBE_COUNT:-?} tests (incl. coalesced-handshake race)"
  record "tools contract + regression tests" PASS "python 3" "${PROBE_COUNT:-?} tests -> $PROBE_LOG"
else
  tail -20 "$PROBE_LOG"
  record "tools contract + regression tests" FAIL "python 3" "see $PROBE_LOG"
fi

# ------------------------------------------------- 3b. Phase 0 evidence (docs)
step_header "Phase 0 evidence (customer discovery happens outside the terminal)"
INTERVIEWS=$(ls research-notes/interviews/*.md 2>/dev/null | grep -viE 'readme|template' | wc -l | tr -d ' ')
INTERVIEWS=${INTERVIEWS:-0}
if grep -q "I'm building a robot that" README.md 2>/dev/null; then
  echo "  ${GREEN}PASS${RESET} README states the chosen task"
  record "Phase 0: niche chosen in README" PASS "docs" "mission sentence present"
else
  echo "  ${YELLOW}PENDING${RESET} README still says the task is not selected"
  record "Phase 0: niche chosen in README" "PENDING" "docs" "blocking every other phase"
fi
if [ "$INTERVIEWS" -ge 5 ]; then
  echo "  ${GREEN}PASS${RESET} $INTERVIEWS/5 customer conversations recorded"
  record "Phase 0: 5 customer conversations" PASS "docs" "$INTERVIEWS recorded in research-notes/interviews/"
else
  echo "  ${YELLOW}PENDING${RESET} $INTERVIEWS/5 customer conversations recorded"
  record "Phase 0: 5 customer conversations" "PENDING" "docs" \
    "$INTERVIEWS/5 -- copy research-notes/customer-discovery-template.md into research-notes/interviews/"
fi

# ------------------------------------------------------------- 4. real ROS 2
step_header "Real ROS 2 smoke test"
ROS2_STATUS="NOT VERIFIED"
python3 tools/ros2_smoke_test.py --artifact-dir "$ARTIFACT_DIR"
ROS2_EXIT=$?
case "$ROS2_EXIT" in
  0)
    ROS2_STATUS="PASS"
    record "ROS 2 pub/sub + commands" PASS "(ros2)" "real DDS -> ros2_smoke.json" ;;
  3)
    if [ "$REQUIRE_ROS2" = "1" ]; then
      echo "  ${RED}FAIL${RESET} --ros2 was requested but rclpy is unavailable"
      ROS2_STATUS="FAIL"
      record "ROS 2 pub/sub + commands" FAIL "(ros2)" "--ros2 requested, rclpy missing"
    else
      echo "  ${YELLOW}NOT VERIFIED HERE${RESET} (rclpy unavailable; re-run with --ros2 on a ROS 2 machine)"
      record "ROS 2 pub/sub + commands" "NOT VERIFIED" "(ros2)" "needs a sourced ROS 2 install"
    fi ;;
  *)
    ROS2_STATUS="FAIL"
    record "ROS 2 pub/sub + commands" FAIL "(ros2)" "smoke test failed" ;;
esac

# ------------------------------------------------------------------- summary
SUMMARY_MD="$ARTIFACT_DIR/SUMMARY.md"
{
  echo "# Verification summary"
  echo
  echo "Generated $(date -u '+%Y-%m-%dT%H:%M:%SZ') by \`tools/verify.sh\`."
  echo
  echo "| proof | transport | status | detail |"
  echo "| --- | --- | --- | --- |"
  for i in "${!NAMES[@]}"; do
    echo "| ${NAMES[$i]} | ${TRANSPORT[$i]} | ${STATUS[$i]} | ${DETAIL[$i]} |"
  done
  echo
  echo "## Milestone claims"
  echo
  echo "- Pipeline decisions, schema, and command schema: verified by logic/proof/ws checks."
  if [ "$ROS2_STATUS" = "PASS" ]; then
    echo "- **ROS 2 publisher/subscriber pair: VERIFIED on this machine over real DDS.**"
    echo "  \`MILESTONES.md\` may tick *'Built a toy ROS 2 publisher/subscriber pair'\*."
  else
    echo "- **ROS 2 publisher/subscriber pair: NOT VERIFIED.** The box stays unchecked"
    echo "  until \`tools/ros2_smoke_test.py\` passes on a machine with ROS 2 installed."
  fi
  echo "- Nothing here says anything about physical hardware; there is no arm yet."
} >"$SUMMARY_MD"

printf '\n%s==> Summary%s\n' "$BOLD" "$RESET"
printf '  %-32s %-10s %-14s %s\n' "PROOF" "TRANSPORT" "STATUS" "DETAIL"
printf '  %s\n' "---------------------------------------------------------------------------"
for i in "${!NAMES[@]}"; do
  color="$GREEN"
  case "${STATUS[$i]}" in
    FAIL) color="$RED" ;;
    "NOT VERIFIED"|PENDING) color="$YELLOW" ;;
  esac
  printf '  %-32s %-10s %s%-14s%s %s\n' \
    "${NAMES[$i]}" "${TRANSPORT[$i]}" "$color" "${STATUS[$i]}" "$RESET" "${DETAIL[$i]}"
done

printf '\n  summary written to %s\n' "$SUMMARY_MD"
if [ "$FAILED" = "1" ]; then
  printf '  %sSOMETHING FAILED%s\n' "$RED" "$RESET"
else
  printf '  %sEverything that could run, passed.%s' "$GREEN" "$RESET"
  if [ "$ROS2_STATUS" = "PASS" ]; then
    printf ' ROS 2 is verified here.\n'
  else
    printf ' ROS 2 is still NOT VERIFIED (run with --ros2 on a ROS 2 machine).\n'
  fi
fi
exit "$FAILED"
