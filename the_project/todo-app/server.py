#!/usr/bin/env python3
"""Minimal Todo App HTTP server."""

import os
import signal
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from pathlib import Path

DEFAULT_PORT = 3000
BASE_DIR = Path(__file__).parent
INDEX_HTML_PATH = BASE_DIR / "index.html"


def get_port():
    raw_port = os.environ.get("PORT", str(DEFAULT_PORT)).strip()

    try:
        return int(raw_port)
    except ValueError:
        print(
            f"ERROR: PORT must be an integer, got {raw_port!r}",
            file=sys.stderr,
        )
        sys.exit(1)


class TodoAppHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "TodoApp/1.0"

    def _send_text(self, text, status=200):
        body = text.encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        port = self.server.server_address[1]

        if path == "/":
            try:
                template = INDEX_HTML_PATH.read_text(encoding="utf-8")
                html = template.replace("{port}", str(port))
            except FileNotFoundError:
                html = "<h1>index.html not found</h1>"
            self._send_html(html)
        elif path == "/healthz":
            self._send_text("OK")
        elif path == "/todos":
            self._send_text("[]")
        else:
            self._send_text("Not Found", status=404)

    def do_HEAD(self):
        self.do_GET()

    def log_message(self, fmt, *args):
        # Чтобы включить логи запросов, раскомментируй строку ниже:
        # super().log_message(fmt, *args)
        pass


def main():
    port = get_port()

    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), TodoAppHandler)
    except OSError as exc:
        print(
            f"ERROR: cannot bind to port {port}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    server.daemon_threads = True

    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))

    bound_port = server.server_address[1]
    print(f"Server started in port {bound_port}", flush=True)

    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()