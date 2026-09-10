#!/usr/bin/env python3
"""
Reader container:
- Читает лог-файл (пишется writer'ом)
- Читает счётчик ping/pong (пишется pingpong'ом)
- При HTTP-запросе отдаёт последнюю строку лога + количество ping/pong
"""

import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

# Путь к лог-файлу (пишется writer'ом)
LOG_FILE = os.environ.get("LOG_FILE", "/shared/log-output.txt")

# Путь к файлу со счётчиком ping/pong (пишется pingpong'ом)
COUNTER_FILE = os.environ.get("COUNTER_FILE", "/shared/pingpong-counter.txt")

# Порт HTTP-сервера
PORT = int(os.environ.get("PORT", "8080"))


def get_timestamp() -> str:
    now = datetime.now(timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def read_last_log_line() -> str:
    """
    Читает последнюю строку из лог-файла.
    Возвращает пустую строку, если файл не существует или пустой.
    """
    if not os.path.exists(LOG_FILE):
        return ""

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            return ""

        # Берём последнюю строку и убираем переносы
        last_line = lines[-1].rstrip('\n\r')
        return last_line
    except (IOError, OSError):
        return ""


def read_pingpong_count() -> int:
    """
    Читает текущее количество ping/pong запросов из файла.
    Возвращает 0, если файл не существует, пустой или содержит невалидные данные.
    """
    try:
        if not os.path.exists(COUNTER_FILE):
            return 0

        with open(COUNTER_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            return 0

        return int(content)
    except (IOError, OSError, ValueError):
        return 0


def format_response() -> str:
    """
    Формирует ответ в требуемом формате:
    2020-03-30T12:15:17.705Z: 8523ecb1-c716-4cb6-a044-b9e83bb98e43.
    Ping / Pongs: 3
    """
    last_line = read_last_log_line()
    count = read_pingpong_count()

    if not last_line:
        # Writer ещё не успел записать ни одной строки
        return f"No log data available yet.\nPing / Pongs: {count}\n"

    # Добавляем точку в конце строки лога, если её там нет (согласно ТЗ)
    if not last_line.endswith('.'):
        last_line = last_line + '.'

    return f"{last_line}\nPing / Pongs: {count}\n"


class LogReaderHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path == "/":
            content = format_response()
            self._send_text(content)

        elif self.path == "/status":
            content = format_response()
            status = {
                "timestamp": get_timestamp(),
                "log_file": LOG_FILE,
                "counter_file": COUNTER_FILE,
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
    print(f"Log file: {LOG_FILE}", flush=True)
    print(f"Counter file: {COUNTER_FILE}", flush=True)

    try:
        server = HTTPServer(("0.0.0.0", PORT), LogReaderHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("Reader stopped.", flush=True)


if __name__ == "__main__":
    main()