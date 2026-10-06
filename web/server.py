#!/usr/bin/env python3
"""Live web viewer for the robo-rl pipeline (standard library only).

Two modes, one code path:

* ``--mode sim``  (default) runs the shared pipeline against an in-process
  transport and simulates a world so the decisions are visible. Works anywhere,
  including environments without ROS 2.
* ``--mode ros2`` mirrors a real ROS 2 graph: it subscribes to the live
  ``detected_object`` topic, feeds those payloads through the same PickerLogic,
  and publishes the browser's buttons onto ``arm_command``. Requires rclpy.

The browser talks to this server over a WebSocket (``/ws``), with an automatic
fallback to ``GET /api/state`` polling for environments where WebSocket upgrade
is blocked by a proxy. Nothing here is a ROS 2 bridge replacement -- see
``docs/VERIFICATION.md`` and ``web/README.md`` for what each mode proves.

Usage:
    python3 web/server.py --mode sim --port 8000
    python3 web/server.py --mode ros2 --port 8000     # needs sourced ROS 2
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import posixpath
import struct
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
PACKAGE_ROOT = os.path.join(REPO_ROOT, "ros2_ws", "src", "robo_rl_demo")
STATIC_ROOT = os.path.join(HERE, "static")

# The shared pipeline lives in the ROS 2 package; put it on the path before
# importing anything that depends on it.
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from pipeline_runner import PipelineRunner  # noqa: E402
from transports import build_transport  # noqa: E402

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
LOOP_HZ = 20.0
BROADCAST_HZ = 10.0
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
    ".ico": "image/x-icon",
}


class WsClient:
    """One connected browser, with a lock so several threads can write safely."""

    def __init__(self, sock) -> None:
        self.sock = sock
        self.alive = True
        self.send_lock = threading.Lock()
        self.subscriptions: List[str] = []

    def send_text(self, text: str) -> None:
        self._send_frame(text.encode("utf-8"), opcode=0x1)

    def send_pong(self, payload: bytes) -> None:
        self._send_frame(payload, opcode=0xA)

    def send_close(self, code: int = 1000) -> None:
        try:
            self._send_frame(struct.pack(">H", code), opcode=0x8)
        except OSError:
            pass
        finally:
            self.alive = False

    def _send_frame(self, payload: bytes, opcode: int) -> None:
        if not self.alive:
            return
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(length)
        elif length < 65536:
            header.append(126)
            header += struct.pack(">H", length)
        else:
            header.append(127)
            header += struct.pack(">Q", length)
        with self.send_lock:
            try:
                self.sock.sendall(bytes(header) + payload)
            except OSError:
                self.alive = False


class ViewerState:
    """Everything shared between the HTTP threads and the simulation loop."""

    def __init__(self, runner: PipelineRunner) -> None:
        self.runner = runner
        self._lock = threading.RLock()
        self._clients: List[WsClient] = []
        self._stop = threading.Event()
        self._last_broadcast = 0.0
        self._state_json = "{}"

    # -- client registry -----------------------------------------------------
    def add_client(self, client: WsClient) -> None:
        with self._lock:
            self._clients.append(client)

    def remove_client(self, client: WsClient) -> None:
        with self._lock:
            if client in self._clients:
                self._clients.remove(client)

    def clients(self) -> List[WsClient]:
        with self._lock:
            return list(self._clients)

    def state(self) -> dict:
        return self.runner.snapshot()

    def state_json(self) -> str:
        with self._lock:
            return self._state_json

    # -- the one loop that steps the world and pushes frames -----------------
    def run_forever(self) -> None:
        dt = 1.0 / LOOP_HZ
        next_tick = time.monotonic()
        while not self._stop.is_set():
            self.runner.step(dt)
            now = time.monotonic()
            if now - self._last_broadcast >= 1.0 / BROADCAST_HZ:
                self._last_broadcast = now
                self._broadcast()
            next_tick += dt
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:  # fell behind; resynchronise instead of spinning
                next_tick = time.monotonic()

    def _broadcast(self) -> None:
        try:
            snapshot = self.state()
            payload = json.dumps({"op": "state", "msg": snapshot}, separators=(",", ":"))
        except Exception as error:  # pragma: no cover - defensive
            payload = json.dumps({"op": "error", "msg": {"error": str(error)}})
        with self._lock:
            self._state_json = payload
            clients = list(self._clients)
        for client in clients:
            if not client.alive:
                self.remove_client(client)
                continue
            client.send_text(payload)

    def stop(self) -> None:
        self._stop.set()


def read_exact(rfile, count: int) -> Optional[bytes]:
    """Read exactly ``count`` bytes, or return None if the peer hung up."""
    data = rfile.read(count)
    if data is None or len(data) < count:
        return None
    return data


def read_frame(rfile):
    """Read one WebSocket frame. Returns (opcode, payload) or None on close."""
    header = read_exact(rfile, 2)
    if header is None:
        return None
    first, second = header[0], header[1]
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F
    if length == 126:
        extended = read_exact(rfile, 2)
        if extended is None:
            return None
        length = struct.unpack(">H", extended)[0]
    elif length == 127:
        extended = read_exact(rfile, 8)
        if extended is None:
            return None
        length = struct.unpack(">Q", extended)[0]
    if length > 4 * 1024 * 1024:  # refuse absurd frames rather than allocate
        return None
    mask_key = read_exact(rfile, 4) if masked else None
    if masked and mask_key is None:
        return None
    payload = read_exact(rfile, length) if length else b""
    if payload is None:
        return None
    if mask_key:
        payload = bytes(byte ^ mask_key[i % 4] for i, byte in enumerate(payload))
    return opcode, payload


class ViewerHandler(BaseHTTPRequestHandler):
    server_version = "robo-rl-viewer/0.1"
    protocol_version = "HTTP/1.1"

    state: ViewerState  # injected on the server class
    quiet = False

    # -- plumbing ------------------------------------------------------------
    def log_message(self, fmt, *args):  # keep the console readable
        if not self.quiet:
            sys.stderr.write(f"[viewer] {fmt % args}\n")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # Never frame-block: this page is meant to be embedded in a preview pane.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _serve_static(self, path: str) -> None:
        relative = path.lstrip("/") or "index.html"
        if relative == "":  # pragma: no cover - defensive
            relative = "index.html"
        candidate = os.path.normpath(os.path.join(STATIC_ROOT, relative))
        if not candidate.startswith(STATIC_ROOT + os.sep) and candidate != STATIC_ROOT:
            self._send_json(403, {"error": "forbidden"})
            return
        if os.path.isdir(candidate):
            candidate = os.path.join(candidate, "index.html")
        if not os.path.isfile(candidate):
            self._send_json(404, {"error": "not found", "path": posixpath.normpath(path)})
            return
        extension = os.path.splitext(candidate)[1].lower()
        with open(candidate, "rb") as handle:
            body = handle.read()
        self._send(200, body, CONTENT_TYPES.get(extension, "application/octet-stream"))

    # -- routes --------------------------------------------------------------
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/ws":
            self._handle_websocket()
            return
        if path == "/api/state":
            self._send_json(200, self.state.state())
            return
        if path == "/api/health":
            snapshot = self.state.state()
            self._send_json(
                200,
                {
                    "ok": True,
                    "mode": snapshot["mode"],
                    "mode_label": snapshot["mode_label"],
                    "is_real_ros": snapshot["is_real_ros"],
                    "ros_available": snapshot["ros_available"],
                    "uptime_s": snapshot["uptime_s"],
                    "tick": snapshot["tick"],
                    "clients": len(self.state.clients()),
                },
            )
            return
        if path.startswith("/api/"):
            self._send_json(404, {"error": "unknown endpoint"})
            return
        self._serve_static(path)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path not in ("/api/command", "/api/resolve_review", "/api/sim_config"):
            self._send_json(404, {"error": "unknown endpoint"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "body must be valid JSON"})
            return

        if path == "/api/resolve_review":
            self.state.runner.timeout_review(resolve=True)
            self._send_json(200, {"ok": True, "action": "resolve_review"})
            return

        if path == "/api/sim_config":
            if not isinstance(body, dict):
                self._send_json(400, {"error": "body must be a JSON object"})
                return
            try:
                result = self.state.runner.configure(
                    rate_hz=body.get("rate_hz"),
                    auto_pause_on_review=body.get("auto_pause_on_review"),
                    reset=bool(body.get("reset", False)),
                )
            except ValueError as error:
                self._send_json(400, {"error": str(error)})
                return
            self._send_json(200, result)
            return

        payload = body.get("command") if isinstance(body, dict) else None
        if payload is None and isinstance(body, dict):
            payload = json.dumps(body)
        try:
            result = self.state.runner.handle_command(payload)
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
            return
        self._send_json(200, result)

    # -- websocket -----------------------------------------------------------
    def _handle_websocket(self) -> None:
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self._send_json(400, {"error": "missing Sec-WebSocket-Key"})
            return
        accept = base64.b64encode(
            hashlib.sha1((key + WS_GUID).encode("ascii")).digest()
        ).decode("ascii")
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        self.wfile.flush()

        client = WsClient(self.connection)
        self.state.add_client(client)
        client.send_text(self.state.state_json())
        try:
            while client.alive:
                frame = read_frame(self.rfile)
                if frame is None:
                    break
                opcode, payload = frame
                if opcode == 0x8:  # close
                    client.send_close()
                    break
                if opcode == 0x9:  # ping
                    client.send_pong(payload)
                    continue
                if opcode == 0xA:  # pong
                    continue
                if opcode in (0x1, 0x2):
                    self._handle_ws_message(client, payload)
        except OSError:
            pass
        finally:
            client.alive = False
            self.state.remove_client(client)
            self.close_connection = True

    def _handle_ws_message(self, client: WsClient, payload: bytes) -> None:
        try:
            message = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            client.send_text(json.dumps({"op": "error", "msg": "invalid JSON frame"}))
            return
        if not isinstance(message, dict):
            client.send_text(json.dumps({"op": "error", "msg": "expected an object"}))
            return
        op = message.get("op")
        if op == "subscribe":
            topic = str(message.get("topic", ""))
            if topic not in client.subscriptions:
                client.subscriptions.append(topic)
            client.send_text(json.dumps({"op": "subscribed", "topic": topic}))
            return
        if op == "publish":  # operator command, same schema as over ROS 2
            self._apply_ws_command(client, message.get("msg"))
            return
        if op == "ping":
            client.send_text(json.dumps({"op": "pong"}))
            return
        client.send_text(json.dumps({"op": "error", "msg": f"unknown op {op!r}"}))

    def _apply_ws_command(self, client: WsClient, message) -> None:
        if message is None:
            client.send_text(json.dumps({"op": "error", "msg": "publish needs msg"}))
            return
        payload = message if isinstance(message, str) else json.dumps(message)
        try:
            result = self.state.runner.handle_command(payload)
        except ValueError as error:
            client.send_text(json.dumps({"op": "error", "msg": str(error)}))
            return
        client.send_text(json.dumps({"op": "ack", "msg": result}))


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="robo-rl live web viewer")
    parser.add_argument("--host", default="0.0.0.0", help="bind address")
    parser.add_argument("--port", type=int, default=8000, help="bind port")
    parser.add_argument(
        "--mode",
        choices=("sim", "ros2"),
        default="sim",
        help="sim = in-process simulation (no ROS 2 needed); ros2 = live rclpy/DDS",
    )
    parser.add_argument("--rate", type=float, default=1.0, help="camera publish rate (Hz)")
    parser.add_argument(
        "--threshold", type=float, default=0.65, help="minimum detection confidence"
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (deterministic demo)")
    parser.add_argument(
        "--auto-pause",
        action="store_true",
        help="pause the line when a low-confidence item needs a human",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress request logging")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        transport = build_transport(args.mode)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 3

    runner = PipelineRunner(
        transport,
        rate_hz=args.rate,
        min_confidence=args.threshold,
        seed=args.seed,
        auto_pause_on_review=args.auto_pause,
    )
    transport.start()
    if transport.is_real_ros:
        runner.selftest = transport.selftest()
        runner.snapshot_extra = {"selftest": runner.selftest}
    state = ViewerState(runner)

    ViewerHandler.state = state
    ViewerHandler.quiet = args.quiet
    server = ThreadingHTTPServer((args.host, args.port), ViewerHandler)
    server.daemon_threads = True

    loop = threading.Thread(target=state.run_forever, name="pipeline-loop", daemon=True)
    loop.start()

    print(f"robo-rl viewer  mode={args.mode}  transport={transport.label}")
    print(f"  http://{args.host}:{args.port}/  (WebSocket at /ws, poll fallback at /api/state)")
    if not transport.is_real_ros:
        print("  NOTE: simulation mode -- ROS 2 is not running. Logic is real, DDS is not.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        state.stop()
        transport.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
