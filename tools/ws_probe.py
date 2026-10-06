#!/usr/bin/env python3
"""Independent WebSocket probe for the robo-rl viewer.

This is deliberately a *from-scratch* WebSocket client that shares no code with
``web/server.py``: an independent client verifies the real wire protocol, where
importing the server's own frame helpers would only prove it is self-consistent.

It connects, subscribes, watches live state frames, then exercises the operator
command round-trip (stop -> expect paused, start -> expect running). Exit code 0
means the browser-facing live path works.

    python3 tools/ws_probe.py --port 8114
    python3 tools/ws_probe.py --port 8114 --seconds 4 --json out.json
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import struct
import time

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def handshake(sock: socket.socket, host: str, port: int, path: str = "/ws") -> bytes:
    """Perform the HTTP Upgrade and verify the server's accept header.

    Returns any bytes that arrived in the same TCP segment as the response.
    Those are real WebSocket frames -- the server pushes its first state frame
    immediately after upgrading -- so they must be fed to the frame reader, not
    mistaken for protocol noise. (Missing this made the probe flaky: it passed
    until the server happened to reply fast enough to coalesce the packets.)
    """
    import hashlib

    key = base64.b64encode(os.urandom(16)).decode("ascii")
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.sendall(request.encode("ascii"))

    buffer = b""
    while b"\r\n\r\n" not in buffer:
        chunk = sock.recv(4096)
        if not chunk:
            raise RuntimeError("server closed the connection during handshake")
        buffer += chunk
    head, _, rest = buffer.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    status = lines[0]
    if "101" not in status:
        raise RuntimeError(f"expected HTTP 101, got: {status}")

    headers = {}
    for line in lines[1:]:
        if ":" in line:
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()

    expected = base64.b64encode(
        hashlib.sha1((key + WS_GUID).encode("ascii")).digest()
    ).decode("ascii")
    if headers.get("sec-websocket-accept") != expected:
        raise RuntimeError(
            "Sec-WebSocket-Accept mismatch: server is not speaking WebSocket correctly"
        )
    return rest


class FrameReader:
    """Reads server frames, starting from bytes that already arrived."""

    def __init__(self, sock: socket.socket, buffer: bytes = b"") -> None:
        self._sock = sock
        self._buffer = bytearray(buffer)

    def _read_exact(self, count: int) -> bytes:
        while len(self._buffer) < count:
            chunk = self._sock.recv(max(4096, count - len(self._buffer)))
            if not chunk:
                raise RuntimeError("server closed the connection")
            self._buffer.extend(chunk)
        data = bytes(self._buffer[:count])
        del self._buffer[:count]
        return data

    def read(self) -> tuple[int, bytes]:
        """Read one frame: (opcode, payload)."""
        header = self._read_exact(2)
        opcode = header[0] & 0x0F
        masked = bool(header[1] & 0x80)
        length = header[1] & 0x7F
        if length == 126:
            length = struct.unpack(">H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self._read_exact(8))[0]
        mask = self._read_exact(4) if masked else None
        payload = self._read_exact(length) if length else b""
        if mask:  # servers must not mask, but cope if one does
            payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        return opcode, payload


def send_text(sock: socket.socket, text: str) -> None:
    """Send a masked text frame (clients must mask; servers must not)."""
    payload = text.encode("utf-8")
    header = bytearray([0x81])
    length = len(payload)
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header += struct.pack(">H", length)
    else:
        header.append(0x80 | 127)
        header += struct.pack(">Q", length)
    mask = os.urandom(4)
    masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    sock.sendall(bytes(header) + mask + masked)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="WebSocket probe for the robo-rl viewer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--path", default="/ws")
    parser.add_argument("--seconds", type=float, default=3.0, help="observation window")
    parser.add_argument("--json", help="write the collected frames to this file")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    say = (lambda *a: None) if args.quiet else print
    checks: list[tuple[str, bool]] = []
    frames: list[dict] = []

    try:
        sock = socket.create_connection((args.host, args.port), timeout=5)
    except OSError as error:
        print(f"FAIL: cannot connect to {args.host}:{args.port} -> {error}")
        return 2

    sock.settimeout(2.0)
    try:
        leftover = handshake(sock, args.host, args.port, args.path)
        reader = FrameReader(sock, leftover)
        checks.append(("websocket handshake accepted", True))
        say("  handshake ok")

        send_text(sock, json.dumps({"op": "subscribe", "topic": "/detected_object"}))

        # Prime a command round-trip: stop, then start, watching real frames.
        deadline = time.monotonic() + args.seconds
        stop_sent = False
        start_sent = False
        saw_stopped = False
        saw_running = False

        while time.monotonic() < deadline:
            try:
                opcode, payload = reader.read()
            except (socket.timeout, RuntimeError):
                continue
            if opcode == 0x8:
                break
            if opcode != 0x1:
                continue
            try:
                frame = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if frame.get("op") != "state":
                continue
            snapshot = frame["msg"]
            frames.append(snapshot)
            elapsed = time.monotonic()

            if len(frames) == 2 and not stop_sent:
                send_text(sock, json.dumps({"op": "publish", "msg": {"action": "stop"}}))
                stop_sent = True
                say(f"  sent stop command at t={snapshot['uptime_s']:.1f}s")
            elif saw_stopped and not start_sent:
                send_text(sock, json.dumps({"op": "publish", "msg": {"action": "start"}}))
                start_sent = True
                say(f"  sent start command at t={snapshot['uptime_s']:.1f}s")

            if stop_sent and not snapshot["running"]:
                saw_stopped = True
            if start_sent and snapshot["running"]:
                saw_running = True
            if stop_sent and not saw_stopped:
                pass  # still waiting for the stop to take effect
            if saw_stopped and start_sent and (saw_running or elapsed > deadline):
                break
    finally:
        try:
            sock.close()
        except OSError:
            pass

    if not frames:
        print("FAIL: no state frames received over the WebSocket")
        return 1

    last = frames[-1]
    checks.append((f"received {len(frames)} live state frames", len(frames) >= 2))
    checks.append(("frames carry a mode and transport label", bool(last.get("mode_label"))))
    checks.append(("counters present in frame", "counters" in last))
    checks.append(("stop command paused the pipeline", bool(saw_stopped)))
    checks.append(("start command resumed the pipeline", bool(saw_running)))
    if last.get("mode") == "sim":
        checks.append(
            ("sim mode self-reports as not-the-real-thing", last.get("is_real_ros") is False)
        )

    say("")
    for name, ok in checks:
        say(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    say("")
    say(
        "  final: mode={mode} running={running} published={published} decisions={decisions}".format(
            mode=last.get("mode"),
            running=last.get("running"),
            published=last.get("counters", {}).get("published"),
            decisions=last.get("counters", {}).get("decisions"),
        )
    )

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump({"frames": len(frames), "checks": checks, "last": last}, handle, indent=2)
        say(f"  wrote {args.json}")

    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
