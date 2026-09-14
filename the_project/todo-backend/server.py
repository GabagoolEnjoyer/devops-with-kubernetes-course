#!/usr/bin/env python3
"""
Todo-backend service:
- GET  /todos   — отдаёт список всех todo (JSON)
- POST /todos   — создаёт новое todo (JSON-тело {"text": "..."}), отвечает 201
- GET  /healthz — health check

Хранилище — память процесса (БД появится позже).
"""

import json
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

DEFAULT_PORT = 8080
MAX_TODO_LEN = 140

# Хранилище в памяти + блокировка (сервер многопоточный)
_todos = []  # [{"id": 1, "text": "..."}, ...]
_next_id = 1
_lock = threading.Lock()


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


class TodoBackendHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "TodoBackend/1.0"

    # ---------- вспомогательные методы ----------

    def _cors_headers(self):
        # Чтобы фронтенд мог обращаться к бэкенду с другого порта при локальной разработке
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()

        if self.command != "HEAD":
            self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length > 0 else b""

    # ---------- HTTP-методы ----------

    def do_OPTIONS(self):
        # CORS preflight от браузера
        self.send_response(204)
        self._cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/todos":
            with _lock:
                snapshot = list(_todos)
            self._send_json(snapshot)

        elif path == "/healthz":
            self._send_json({"status": "OK"})

        else:
            self._send_json({"error": "Not Found"}, status=404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path != "/todos":
            self._send_json({"error": "Not Found"}, status=404)
            return

        raw = self._read_body()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._send_json({"error": "Body must be valid JSON"}, status=400)
            return

        text = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(text, str):
            self._send_json({"error": "Field 'text' (string) is required"}, status=400)
            return

        text = text.strip()
        if not text:
            self._send_json({"error": "Todo must not be empty"}, status=400)
            return
        if len(text) > MAX_TODO_LEN:
            self._send_json(
                {"error": f"Todo must not be longer than {MAX_TODO_LEN} characters"},
                status=400,
            )
            return

        global _next_id
        with _lock:
            todo = {"id": _next_id, "text": text}
            _next_id += 1
            _todos.append(todo)

        print(f"Created todo #{todo['id']}: {text}", flush=True)
        self._send_json(todo, status=201)

    def do_HEAD(self):
        self.do_GET()

    def log_message(self, fmt, *args):
        print(f"{self.client_address[0]} - {fmt % args}", flush=True)


def main():
    port = get_port()

    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), TodoBackendHandler)
    except OSError as exc:
        print(
            f"ERROR: cannot bind to port {port}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    server.daemon_threads = True

    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))

    print(f"Todo-backend started on port {port}", flush=True)
    print(f"Storage: in-memory ({len(_todos)} todos)", flush=True)

    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()