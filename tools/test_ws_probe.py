#!/usr/bin/env python3
"""Regression tests for tools/ws_probe.py.

These exist because of a real, timing-dependent failure: the viewer sends its
first state frame immediately after the WebSocket upgrade, and when that frame
shares a TCP segment with the handshake response, a naive client either crashes
on the "trailing bytes" or silently drops the frame. It passed for a while and
then failed about one run in three -- the worst kind of bug, and exactly why the
probe shares no code with the server.

The fake server below reproduces that coalescing deterministically, so the fix
stays fixed regardless of machine speed.

    python3 -m unittest discover -s tools -p 'test_*.py' -v
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ws_probe import FrameReader, handshake  # noqa: E402

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def encode_server_frame(payload: bytes, opcode: int = 0x1) -> bytes:
    """Server frames are unmasked."""
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
    return bytes(header) + payload


class CoalescingServer(threading.Thread):
    """Replies with handshake response *and* a state frame in one sendall()."""

    def __init__(self, frame_payloads: list[str], split: bool) -> None:
        super().__init__(daemon=True)
        self.frame_payloads = frame_payloads
        self.split = split
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]

    def run(self) -> None:
        try:
            connection, _ = self.sock.accept()
        except OSError:
            return
        with connection:
            request = b""
            while b"\r\n\r\n" not in request:
                chunk = connection.recv(4096)
                if not chunk:
                    return
                request += chunk
            key = ""
            for line in request.decode("latin-1").split("\r\n"):
                if line.lower().startswith("sec-websocket-key:"):
                    key = line.split(":", 1)[1].strip()
            accept = base64.b64encode(
                hashlib.sha1((key + WS_GUID).encode("ascii")).digest()
            ).decode("ascii")
            head = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
            ).encode("ascii")
            frames = b"".join(
                encode_server_frame(payload.encode("utf-8"))
                for payload in self.frame_payloads
            )
            if self.split:
                connection.sendall(head)
                connection.sendall(frames)
            else:
                connection.sendall(head + frames)  # the failing case
            # keep the socket open until the client is done reading
            try:
                connection.recv(1024)
            except OSError:
                pass


class CoalescedHandshakeTests(unittest.TestCase):
    def _collect(self, split: bool, count: int = 3) -> list[dict]:
        payloads = [
            json.dumps({"op": "state", "msg": {"tick": index}}) for index in range(count)
        ]
        server = CoalescingServer(payloads, split=split)
        server.start()
        try:
            sock = socket.create_connection(("127.0.0.1", server.port), timeout=5)
            sock.settimeout(2)
            with sock:
                leftover = handshake(sock, "127.0.0.1", server.port)
                reader = FrameReader(sock, leftover)
                collected = []
                for _ in range(count):
                    opcode, payload = reader.read()
                    self.assertEqual(opcode, 0x1)
                    collected.append(json.loads(payload.decode("utf-8")))
                return collected
        finally:
            server.sock.close()

    def test_frames_coalesced_with_handshake_are_not_lost(self):
        """The exact bug: handshake response and first frame in one packet."""
        frames = self._collect(split=False)
        self.assertEqual([f["msg"]["tick"] for f in frames], [0, 1, 2])

    def test_frames_sent_separately_still_work(self):
        frames = self._collect(split=True)
        self.assertEqual([f["msg"]["tick"] for f in frames], [0, 1, 2])

    def test_handshake_returns_leftover_bytes(self):
        server = CoalescingServer([json.dumps({"op": "state", "msg": {"tick": 0}})], split=False)
        server.start()
        try:
            sock = socket.create_connection(("127.0.0.1", server.port), timeout=5)
            sock.settimeout(2)
            with sock:
                leftover = handshake(sock, "127.0.0.1", server.port)
                self.assertTrue(leftover, "expected the frame bytes to be buffered")
                self.assertIn(b"\x81", leftover[:1] + leftover[1:2])
        finally:
            server.sock.close()

    def test_rejects_non_websocket_response(self):
        class PlainServer(threading.Thread):
            def __init__(self) -> None:
                super().__init__(daemon=True)
                self.sock = socket.socket()
                self.sock.bind(("127.0.0.1", 0))
                self.sock.listen(1)
                self.port = self.sock.getsockname()[1]

            def run(self) -> None:
                connection, _ = self.sock.accept()
                with connection:
                    connection.recv(4096)
                    connection.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")

        server = PlainServer()
        server.start()
        try:
            sock = socket.create_connection(("127.0.0.1", server.port), timeout=5)
            with sock:
                with self.assertRaises(RuntimeError):
                    handshake(sock, "127.0.0.1", server.port)
        finally:
            server.sock.close()


if __name__ == "__main__":
    unittest.main()
