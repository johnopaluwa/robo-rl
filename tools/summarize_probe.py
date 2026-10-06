#!/usr/bin/env python3
"""Print a probe artifact as markdown, for CI job summaries.

    python3 tools/summarize_probe.py artifacts/proofs/ros2_viewer_probe.json

Kept as a file rather than an inline heredoc in the workflow, because a heredoc
inside a YAML block scalar is an indentation trap waiting to happen.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", nargs="?", default="artifacts/proofs/ros2_viewer_probe.json")
    parser.add_argument(
        "--title", default="Browser path over live DDS", help="markdown heading text"
    )
    args = parser.parse_args(argv)

    if not os.path.isfile(args.artifact):
        print(f"### {args.title}\n\nNo artifact at `{args.artifact}` -- the check did not finish.")
        return 0

    with open(args.artifact, encoding="utf-8") as handle:
        data = json.load(handle)

    checks = data.get("checks", [])
    passed = sum(1 for _, ok in checks if ok)
    print(f"### {args.title}")
    print()
    print(f"- artifact: `{args.artifact}`")
    print(f"- frames received: {data.get('frames', '?')}")
    print(f"- checks: {passed}/{len(checks)} passed")
    print()
    for name, ok in checks:
        print(f"- {'PASS' if ok else 'FAIL'}: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
