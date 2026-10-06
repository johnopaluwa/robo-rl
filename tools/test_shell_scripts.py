#!/usr/bin/env python3
"""Guards for the shell scripts in tools/.

Two checks, both aimed at failures that actually happened in this repo:

1. ``bash -n`` on every script -- a syntax error should never reach CI.

2. **No variable is used before it is assigned.** This is the bug that broke the
   ROS 2 browser-path check twice: once inheriting it from ROS 2's own setup
   scripts, and once of my own making, with a ``note "... ${DDS_WAIT}s"`` line
   placed above the ``DDS_WAIT=${DDS_WAIT:-30}`` that defines it. Under
   ``set -u`` that aborts the whole script with status 1 and a stderr line only,
   so the diagnostics file simply stops mid-sentence -- silent failure, the worst
   kind.

   Shellcheck does not catch that case, because the variable *is* assigned
   somewhere in the file; only the order is wrong. So the rule is checked here,
   on purpose: a name that is assigned later in the file than it is used is a
   bug, full stop. Names that are never assigned anywhere are left alone, since
   they are legitimately environment variables or script arguments.

    python3 -m unittest discover -s tools -p 'test_*.py' -v
"""

from __future__ import annotations

import os
import re
import subprocess
import unittest

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = sorted(
    os.path.join(TOOLS_DIR, name)
    for name in os.listdir(TOOLS_DIR)
    if name.endswith(".sh")
)

ASSIGN = re.compile(
    r"""(?:^|[\s;&|(])           # a command boundary
        (?:(?:local|export|readonly|declare)\s+(?:-\w+\s+)*)?
        ([A-Za-z_][A-Za-z0-9_]*)=   # NAME=
    """,
    re.VERBOSE,
)
# for/read also bind names
BIND = re.compile(r"\b(?:for|read)\s+(?:-\w+\s+)*([A-Za-z_][A-Za-z0-9_]*)\b")
# ${NAME}, $NAME -- but not ${NAME:-default}, ${#NAME}, ${NAME[0]}, ${!NAME}
USE = re.compile(
    r"""
    \$\{([A-Za-z_][A-Za-z0-9_]*)(?![A-Za-z0-9_\[\]:+\-?=#])   # ${NAME}
    |
    (?<!\$)\$([A-Za-z_][A-Za-z0-9_]*)                          # $NAME
    """,
    re.VERBOSE,
)
SPECIAL = {"?", "$", "!", "#", "*", "@", "-", "0", "1", "2", "3"}


def strip_comment(line: str) -> str:
    """Drop a trailing shell comment, ignoring # inside quotes."""
    out = []
    quote = None
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            if char == quote:
                quote = None
            out.append(char)
        elif char in "\"'":
            quote = char
            out.append(char)
        elif char == "#" and (index == 0 or line[index - 1] in " \t"):
            break
        else:
            out.append(char)
        index += 1
    return "".join(out)


def analyse(path: str) -> tuple[dict, list]:
    """Return (first assignment line per name, [(name, line, text)] uses)."""
    with open(path, encoding="utf-8") as handle:
        lines = handle.readlines()

    first_assignment: dict[str, int] = {}
    uses: list[tuple[str, int, str]] = []

    for number, raw in enumerate(lines, start=1):
        line = strip_comment(raw)
        for match in ASSIGN.finditer(line):
            first_assignment.setdefault(match.group(1), number)
        for match in BIND.finditer(line):
            first_assignment.setdefault(match.group(1), number)
        for match in USE.finditer(line):
            name = match.group(1) or match.group(2)
            if name in SPECIAL:
                continue
            uses.append((name, number, raw.rstrip()))
    return first_assignment, uses


class SyntaxTests(unittest.TestCase):
    def test_scripts_exist(self):
        self.assertTrue(SCRIPTS, "no shell scripts found in tools/")

    def test_every_script_parses(self):
        for script in SCRIPTS:
            with self.subTest(script=os.path.basename(script)):
                result = subprocess.run(
                    ["bash", "-n", script], capture_output=True, text=True
                )
                self.assertEqual(
                    result.returncode, 0, f"bash -n failed:\n{result.stderr}"
                )


class UseBeforeAssignTests(unittest.TestCase):
    def test_no_variable_is_used_before_it_is_assigned(self):
        problems = []
        for script in SCRIPTS:
            first_assignment, uses = analyse(script)
            for name, line, text in uses:
                assigned_at = first_assignment.get(name)
                if assigned_at is None:
                    continue  # exported env var or external input: not our business
                if assigned_at > line:
                    problems.append(
                        f"{os.path.basename(script)}:{line}: '{name}' is used "
                        f"but only assigned later (line {assigned_at}): {text.strip()}"
                    )
        self.assertEqual(
            problems,
            [],
            "a variable is used before it is assigned, which under `set -u` "
            "aborts the script silently:\n" + "\n".join(problems),
        )

    def test_the_checker_detects_the_bug_it_is_here_for(self):
        """Keep the guard honest: it must flag use-before-assign, and only then."""
        sample_bug = 'note "waiting up to ${DDS_WAIT}s ..."\nDDS_WAIT=${DDS_WAIT:-30}\n'
        sample_ok = 'DDS_WAIT=${DDS_WAIT:-30}\nnote "waiting up to ${DDS_WAIT}s ..."\n'

        with self.subTest("flags the ordering bug"):
            path = os.path.join(TOOLS_DIR, "_probe_bug.sh")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(sample_bug)
            try:
                first_assignment, uses = analyse(path)
                offending = [
                    name
                    for name, line, _ in uses
                    if (at := first_assignment.get(name)) is not None and at > line
                ]
                self.assertEqual(offending, ["DDS_WAIT"])
            finally:
                os.remove(path)

        with self.subTest("does not flag the correct order"):
            path = os.path.join(TOOLS_DIR, "_probe_ok.sh")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(sample_ok)
            try:
                first_assignment, uses = analyse(path)
                offending = [
                    name
                    for name, line, _ in uses
                    if (at := first_assignment.get(name)) is not None and at > line
                ]
                self.assertEqual(offending, [])
            finally:
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
