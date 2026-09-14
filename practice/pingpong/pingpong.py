#!/usr/bin/env python3
"""
Ping-pong service:
- GET /pingpong — увеличивает счётчик и отвечает "pong N"
- GET /pings    — отдаёт текущее количество pong БЕЗ инкремента (для log-output)
- GET /healthz  — health check
"""

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock

# Порт HTTP-сервера
PORT = int(os.environ.get("PORT", "8080"))

# Счётчик запросов (живёт в памяти, файл больше не используется)
counter = 0
counter_lock = Lock()


class PingPongHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        global counter

        if self.path == "/pingpong":
            # Увеличиваем счётчик
            with counter_lock:
                counter += 1
                current_count = counter
            self._send_text(f"pong {current_count}")

        elif self.path in ("/pings", "/count"):
            # Только отдаём текущее значение, не увеличивая
            with counter_lock:
                current_count = counter
            self._send_text(str(current_count))

        elif self.path == "/healthz":
            self._send_text("OK")

        else:
            self._send_text("Not Found", status=404)

    def _send_text(self, text, status=200):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Логи запросов в stdout
        print(f"{self.client_address[0]} - {args[0]}", flush=True)


def main():
    # ThreadingHTTPServer: каждое соединение в своём потоке,
    # keep-alive от Traefik больше не блокирует остальных клиентов
    server = ThreadingHTTPServer(("0.0.0.0", PORT), PingPongHandler)
    server.daemon_threads = True
    print(f"Ping-pong server started on port {PORT}", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...", flush=True)
        server.shutdown()


if __name__ == "__main__":
    main()