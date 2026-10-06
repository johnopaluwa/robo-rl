#!/usr/bin/env python3
"""Contract tests between the web viewer's frontend and backend.

The viewer is hand-written HTML/JS with no build step, so nothing would catch a
typo'd element id, a command action that does not exist, or an endpoint that was
renamed in the server. Those bugs are invisible until someone opens the page --
which is exactly the failure mode this repo is trying to avoid.

What is checked:

1. every ``el("...")`` id in ``app.js`` exists in ``index.html``
2. every command action the UI sends is accepted by ``parse_command``
3. every ``/api/...`` endpoint the UI calls exists in ``server.py``
4. the page loads no external assets (the preview sandbox has no CDN access)

    python3 -m unittest discover -s tools -p 'test_*.py' -v
"""

from __future__ import annotations

import os
import re
import sys
import unittest

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TOOLS_DIR)
PACKAGE_ROOT = os.path.join(REPO_ROOT, "ros2_ws", "src", "robo_rl_demo")
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)

from robo_rl_demo.pipeline import VALID_COMMAND_ACTIONS  # noqa: E402

INDEX = os.path.join(REPO_ROOT, "web", "static", "index.html")
APP_JS = os.path.join(REPO_ROOT, "web", "static", "app.js")
SERVER = os.path.join(REPO_ROOT, "web", "server.py")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class ElementIdContractTests(unittest.TestCase):
    def test_every_referenced_element_id_exists(self):
        html = read(INDEX)
        script = read(APP_JS)
        defined = set(re.findall(r'id="([^"]+)"', html))
        referenced = set(re.findall(r'el\("([^"]+)"\)', script))
        missing = sorted(referenced - defined)
        self.assertEqual(
            missing,
            [],
            f"app.js references ids that index.html does not define: {missing}",
        )

    def test_referenced_ids_are_not_obviously_unused(self):
        """Every id in the HTML is referenced from the script, or from the SVG."""
        html = read(INDEX)
        script = read(APP_JS)
        defined = set(re.findall(r'id="([^"]+)"', html))
        referenced = set(re.findall(r'el\("([^"]+)"\)', script))
        # SVG defs are referenced from markup, e.g. fill="url(#beltGrad)"
        referenced |= set(re.findall(r'url\(#([^)]+)\)', html))
        orphans = sorted(defined - referenced)
        self.assertEqual(orphans, [], f"index.html defines unused ids: {orphans}")


class CommandContractTests(unittest.TestCase):
    def test_ui_only_sends_supported_actions(self):
        script = read(APP_JS)
        actions = set(re.findall(r'action:\s*"([^"]+)"', script))
        self.assertTrue(actions, "expected the UI to send at least one command action")
        unsupported = sorted(actions - set(VALID_COMMAND_ACTIONS))
        self.assertEqual(
            unsupported,
            [],
            f"app.js sends actions the pipeline does not accept: {unsupported}",
        )


class EndpointContractTests(unittest.TestCase):
    def test_every_endpoint_the_ui_calls_exists_in_the_server(self):
        script = read(APP_JS)
        server = read(SERVER)
        called = set(re.findall(r'"(/api/[a-z_]+)"', script))
        self.assertTrue(called, "expected the UI to call at least one API endpoint")
        missing = sorted(endpoint for endpoint in called if f'"{endpoint}"' not in server)
        self.assertEqual(missing, [], f"app.js calls endpoints the server lacks: {missing}")


class OfflineSafetyTests(unittest.TestCase):
    def test_page_loads_no_external_assets(self):
        """The preview sandbox cannot reach CDNs, so everything must be local."""
        html = read(INDEX)
        external = re.findall(r'(?:src|href)="(https?://[^"]+|//[^"]+)"', html)
        self.assertEqual(external, [], f"index.html loads external assets: {external}")

    def test_app_js_calls_no_external_urls(self):
        script = read(APP_JS)
        # NB: http://www.w3.org/2000/svg is the SVG namespace *identifier*, not a
        # URL that is ever fetched, so it is excluded deliberately.
        hits = re.findall(r'https?://([a-z0-9.-]+\.[a-z]{2,})', script)
        external = sorted({host for host in hits if host != "www.w3.org"})
        self.assertEqual(external, [], f"app.js references external hosts: {external}")


if __name__ == "__main__":
    unittest.main()
