#!/usr/bin/env python3
"""Simple local server launcher for the RTS demo.

Features:
- Serves current directory on 0.0.0.0
- Auto-finds free port starting from 4173
- Prints localhost and LAN URLs
"""

from __future__ import annotations

import contextlib
import http.server
import os
import socket
import socketserver

START_PORT = int(os.environ.get("PORT", "4173"))


def find_free_port(start: int) -> int:
    port = start
    while port < start + 200:
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                port += 1
    raise RuntimeError("Could not find a free port in range")


def get_lan_ip() -> str:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as s:
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        print(f"[http] {self.address_string()} - {fmt % args}")


def main() -> None:
    port = find_free_port(START_PORT)
    lan_ip = get_lan_ip()

    print("\nStarfront Mobile RTS server is starting...")
    print(f"Local:  http://localhost:{port}")
    print(f"Phone:  http://{lan_ip}:{port}   (same Wi-Fi)")
    print("Press Ctrl+C to stop.\n")

    with socketserver.TCPServer(("0.0.0.0", port), QuietHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
