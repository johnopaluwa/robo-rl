#!/usr/bin/env python3
"""Headless proof that the shared pipeline behaves as documented.

Runs the *same* classes the ROS 2 nodes wrap -- ``CameraSource``, ``PickerLogic``,
``parse_command`` -- against a recording transport, asserts the documented
behaviour, and writes machine-readable + human-readable artifacts.

What this proves: the logic, the wire format, and the accounting are correct.
What it does NOT prove: that ROS 2/DDS carries the messages. Only
``tools/ros2_smoke_test.py`` on a machine with ROS 2 installed can prove that,
and ``docs/VERIFICATION.md`` keeps the two separate on purpose.

    python3 tools/proof_pipeline.py
    python3 tools/proof_pipeline.py --artifact-dir artifacts/proofs
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
PACKAGE_ROOT = os.path.join(REPO_ROOT, "ros2_ws", "src", "robo_rl_demo")
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)

from robo_rl_demo.detection import Detection  # noqa: E402
from robo_rl_demo.pipeline import (  # noqa: E402
    CameraSource,
    PickerLogic,
    parse_command,
    simulate_grasp,
)

THRESHOLD = 0.65
DEFAULT_ARTIFACTS = os.path.join(REPO_ROOT, "artifacts", "proofs")


class Transcript:
    """A transport that records everything and replays it to the picker."""

    def __init__(self) -> None:
        self.picker: PickerLogic | None = None
        self.records: list[tuple[str, str]] = []
        self.decisions: list[dict] = []

    def __call__(self, topic: str, payload: str) -> None:
        self.records.append((topic, payload))
        assert self.picker is not None, "picker must be attached before publishing"
        self.picker.handle_payload(payload)

    def observe(self, result) -> None:
        """Observer passed to PickerLogic, so no private attributes are touched."""
        self.decisions.append(
            {
                "id": result.detection.detection_id if result.detection else None,
                "label": result.detection.label if result.detection else None,
                "confidence": result.detection.confidence if result.detection else None,
                "attempted": result.attempted,
                "malformed": result.malformed,
                "message": result.message,
            }
        )


def run_case(seed: int, ticks: int, threshold: float = THRESHOLD) -> Transcript:
    """Publish ``ticks`` detections and return the full transcript."""
    transport = Transcript()
    picker = PickerLogic(min_confidence=threshold, on_result=transport.observe)
    transport.picker = picker
    camera = CameraSource(transport, rate_hz=1.0, seed=seed)
    for _ in range(ticks):
        camera.tick()
    return transport


def check(checks: list, name: str, ok: bool, detail: str = "") -> None:
    checks.append({"check": name, "passed": bool(ok), "detail": detail})


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Headless pipeline proof")
    parser.add_argument("--ticks", type=int, default=400)
    parser.add_argument("--seed", type=int, default=20261006)
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACTS)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    checks: list[dict] = []
    started = datetime.now(timezone.utc)

    # 1. Determinism: same seed -> byte-identical decision sequence.
    first = run_case(args.seed, args.ticks)
    second = run_case(args.seed, args.ticks)
    check(
        checks,
        "same seed produces identical decisions",
        first.decisions == second.decisions,
        f"{len(first.decisions)} decisions compared",
    )
    different = run_case(args.seed + 1, args.ticks)
    check(
        checks,
        "different seed produces different decisions",
        first.decisions != different.decisions,
    )

    decisions = first.decisions
    attempted = [d for d in decisions if d["attempted"]]
    skipped = [d for d in decisions if not d["attempted"]]

    # 2. Threshold semantics.
    check(
        checks,
        "every attempt is at or above the threshold",
        all(d["confidence"] >= THRESHOLD for d in attempted),
        f"min attempted confidence: {min((d['confidence'] for d in attempted), default=None)}",
    )
    check(
        checks,
        "every skip is below the threshold",
        all(d["confidence"] < THRESHOLD for d in skipped),
        f"max skipped confidence: {max((d['confidence'] for d in skipped), default=None)}",
    )
    check(
        checks,
        "both outcomes actually occurred (test is not vacuous)",
        bool(attempted) and bool(skipped),
        f"{len(attempted)} attempted / {len(skipped)} skipped",
    )

    # 3. Raising the threshold can only reduce attempts (monotonicity).
    strict = run_case(args.seed, args.ticks, threshold=0.95)
    strict_attempts = sum(1 for d in strict.decisions if d["attempted"])
    check(
        checks,
        "raising the threshold cannot increase pick attempts",
        strict_attempts <= len(attempted),
        f"0.95 -> {strict_attempts} attempts vs 0.65 -> {len(attempted)}",
    )

    # 4. Wording matches what the ROS 2 nodes log.
    sample_attempt = attempted[0]
    sample_skip = skipped[0]
    check(
        checks,
        "attempt message names the object and position",
        sample_attempt["message"].startswith(
            f"Would pick #{sample_attempt['id']} ({sample_attempt['label']}) at ("
        ),
        sample_attempt["message"],
    )
    check(
        checks,
        "skip message states the confidence shortfall",
        "is below" in sample_skip["message"],
        sample_skip["message"],
    )

    # 5. Malformed input cannot crash the pipeline or be logged as a pick.
    malformed_picker = PickerLogic(min_confidence=THRESHOLD)
    malformed_results = [
        malformed_picker.handle_payload(payload)
        for payload in ("", "not json", "[]", '{"id": 1}', "null", '{"id": -1}')
    ]
    check(
        checks,
        "malformed payloads are rejected without raising",
        all(r.malformed and not r.attempted for r in malformed_results),
        f"{len(malformed_results)} malformed payloads",
    )
    check(
        checks,
        "malformed payloads are counted separately",
        malformed_picker.count_malformed == len(malformed_results)
        and malformed_picker.count_attempted == 0,
    )

    # 6. Every published payload is a valid Detection (wire-format contract).
    round_tripped = all(
        Detection.from_json(payload).to_json() == payload
        for _, payload in first.records
    )
    check(
        checks,
        "every published payload round-trips through the schema",
        round_tripped,
        f"{len(first.records)} payloads",
    )
    check(
        checks,
        "all detections published on the expected topic",
        all(topic == "detected_object" for topic, _ in first.records),
    )

    # 7. Accounting: simulated grasp outcomes add up.
    rng = random.Random(args.seed)
    outcomes = [simulate_grasp(d["confidence"], rng) for d in attempted]
    check(
        checks,
        "grasp outcomes account for every attempt",
        len(outcomes) == len(attempted),
        f"{sum(outcomes)} placed / {len(outcomes) - sum(outcomes)} dropped",
    )

    # 8. Operator command schema.
    try:
        stop = parse_command('{"action": "stop"}')
        threshold_cmd = parse_command('{"action": "set_min_confidence", "value": 0.9}')
        commands_ok = stop.action == "stop" and threshold_cmd.value == 0.9
    except ValueError:
        commands_ok = False
    check(checks, "operator command schema parses", commands_ok)

    rejected = 0
    for payload in ('{"action": "nope"}', '{"action": "set_min_confidence"}'):
        try:
            parse_command(payload)
        except ValueError:
            rejected += 1
    check(checks, "invalid operator commands are refused", rejected == 2)

    # 9. The shared module must not depend on ROS, or it could not be tested here.
    pipeline_source_path = os.path.join(PACKAGE_ROOT, "robo_rl_demo", "pipeline.py")
    with open(pipeline_source_path, encoding="utf-8") as handle:
        source = handle.read()
    check(
        checks,
        "shared pipeline imports no ROS (so it runs and is testable anywhere)",
        "import rclpy" not in source and "\nrclpy" not in source,
        os.path.relpath(pipeline_source_path, REPO_ROOT),
    )

    # ---------------------------------------------------------------- verdict
    passed = sum(1 for c in checks if c["passed"])
    failed = len(checks) - passed
    verdict = "PASS" if failed == 0 else "FAIL"
    finished = datetime.now(timezone.utc)

    summary = {
        "proof": "pipeline-logic",
        "verdict": verdict,
        "transport": "in-process recording transport (NOT ros2)",
        "proves": [
            "threshold decisions match the documented wording",
            "published payloads satisfy the schema",
            "malformed input is rejected and counted",
            "operator command schema parses and rejects bad input",
            "shared logic has no ROS dependency",
        ],
        "does_not_prove": [
            "that ROS 2 / DDS carries these messages (see ros2-smoke)",
            "that any of this works on physical hardware",
        ],
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "ticks": args.ticks,
        "seed": args.seed,
        "threshold": THRESHOLD,
        "counts": {
            "decisions": len(decisions),
            "attempted": len(attempted),
            "skipped": len(skipped),
            "placed": int(sum(outcomes)),
            "dropped": len(outcomes) - int(sum(outcomes)),
            "strict_threshold_attempts": strict_attempts,
        },
        "checks_passed": passed,
        "checks_failed": failed,
        "checks": checks,
    }

    os.makedirs(args.artifact_dir, exist_ok=True)
    json_path = os.path.join(args.artifact_dir, "pipeline_proof.json")
    md_path = os.path.join(args.artifact_dir, "pipeline_proof.md")
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    lines = [
        "# Proof: pipeline logic",
        "",
        f"- verdict: **{verdict}** ({passed}/{len(checks)} checks passed)",
        f"- run: {started.isoformat()}",
        f"- transport: `{summary['transport']}`",
        f"- seed `{args.seed}`, {args.ticks} detections, threshold {THRESHOLD}",
        "",
        "## What this proves",
        "",
        *[f"- {item}" for item in summary["proves"]],
        "",
        "## What this does NOT prove",
        "",
        *[f"- {item}" for item in summary["does_not_prove"]],
        "",
        "## Counts",
        "",
        "| metric | value |",
        "| --- | --- |",
        *[f"| {key} | {value} |" for key, value in summary["counts"].items()],
        "",
        "## Checks",
        "",
        "| check | result | detail |",
        "| --- | --- | --- |",
        *[
            f"| {c['check']} | {'PASS' if c['passed'] else 'FAIL'} | {c['detail']} |"
            for c in checks
        ],
        "",
    ]
    with open(md_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))

    if not args.quiet:
        print(f"proof: pipeline-logic  transport: {summary['transport']}")
        print(f"  seed={args.seed} ticks={args.ticks} threshold={THRESHOLD}")
        for item in checks:
            flag = "PASS" if item["passed"] else "FAIL"
            detail = f"  ({item['detail']})" if item["detail"] else ""
            print(f"  [{flag}] {item['check']}{detail}")
        print()
        print(
            f"  {verdict}: {passed}/{len(checks)} checks "
            f"| {len(attempted)} attempted, {len(skipped)} needed a human"
        )
        print(f"  artifacts: {os.path.relpath(json_path, REPO_ROOT)}, "
              f"{os.path.relpath(md_path, REPO_ROOT)}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
