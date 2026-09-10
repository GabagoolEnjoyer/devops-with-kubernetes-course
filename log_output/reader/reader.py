#!/usr/bin/env python3
"""
Reader container:
- Читает общий файл
- Отдаёт его содержимое по HTTP GET /
"""

import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

# Тот же путь, что и у writer
LOG_FILE = os.environ.get("LOG_FILE", "/shared/log-output.txt")

# Порт HTTP-сервера
PORT = int(os.environ.get("PORT", "8080"))

# Сколько последних строк отдавать (0 = все)
TAIL_LINES = int(os.environ.get("TAIL_LINES", "10"))


def get_timestamp() -> str:
    now = datetime.now(timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def read_log_file() -> str:
    """Читает файл и возвращает содержимое (последние N строк)."""
    if not os.path.exists(LOG_FILE):
        return ""

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (IOError, OSError):
        return ""

    if TAIL_LINES > 0:
        lines = lines[-TAIL_LINES:]

    return "".join(lines)


class LogReaderHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path == "/":
            content = read_log_file()

            if content:
                self._send_text(content)
            else:
                self._send_text("No log data available yet.\n")

        elif self.path == "/status":
            content = read_log_file()
            status = {
                "timestamp": get_timestamp(),
                "log_file": LOG_FILE,
                "file_exists": os.path.exists(LOG_FILE),
                "tail_lines": TAIL_LINES,
                "content": content
            }
            self._send_json(status)

        elif self.path == "/healthz":
            self._send_text("OK\n")

        else:
            self._send_text("Not Found\n", status=404)

    def _send_text(self, text, status=200):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Отключаем стандартное логирование запросов
        pass


def main() -> None:
    print(f"Reader started on port {PORT}", flush=True)
    print(f"Reading from file: {LOG_FILE}", flush=True)
    print(f"Tail lines: {TAIL_LINES}", flush=True)

    try:
        server = HTTPServer(("0.0.0.0", PORT), LogReaderHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("Reader stopped.", flush=True)


if __name__ == "__main__":
    main()