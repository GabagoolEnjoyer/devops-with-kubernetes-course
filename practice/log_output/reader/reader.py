#!/usr/bin/env python3
"""
Reader container:
- Читает лог-файл (пишется writer'ом)
- Ходит по HTTP в ping-pong сервис за количеством pong (GET /pings)
- Читает файл information.txt и env MESSAGE из ConfigMap
- При HTTP-запросе отдаёт всё вместе в требуемом формате
"""

import json
import os
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Путь к лог-файлу (пишется writer'ом, общий volume внутри пода)
LOG_FILE = os.environ.get("LOG_FILE", "/shared/log-output.txt")

# Путь к файлу information.txt из ConfigMap (смонтирован как volume)
CONFIG_FILE = os.environ.get("CONFIG_FILE", "/usr/src/app/config/information.txt")

# Env-переменная MESSAGE из ConfigMap
MESSAGE = os.environ.get("MESSAGE", "")

# Адрес ping-pong сервиса (DNS-имя сервиса внутри кластера)
PINGPONG_URL = os.environ.get("PINGPONG_URL", "http://pingpong-svc:4444/pings")

# Таймаут запроса к ping-pong, чтобы не подвешивать входящие запросы
PINGPONG_TIMEOUT = float(os.environ.get("PINGPONG_TIMEOUT", "3"))

# Порт HTTP-сервера
PORT = int(os.environ.get("PORT", "8080"))


def get_timestamp() -> str:
    now = datetime.now(timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def read_config_file() -> str:
    """
    Читает содержимое файла information.txt, смонтированного из ConfigMap.
    Возвращает пустую строку, если файла нет или он пустой.
    """
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except (IOError, OSError):
        return ""


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

        return lines[-1].rstrip("\n\r")
    except (IOError, OSError):
        return ""


def fetch_pong_count() -> int:
    """
    HTTP GET к ping-pong сервису за количеством pong.
    Возвращает 0, если сервис недоступен или ответил нечислом.
    """
    try:
        with urllib.request.urlopen(PINGPONG_URL, timeout=PINGPONG_TIMEOUT) as resp:
            content = resp.read().decode("utf-8").strip()
        return int(content)
    except (OSError, ValueError) as e:
        # URLError, timeout, connection refused, невалидное число — все сюда
        print(f"Warning: cannot fetch pong count from {PINGPONG_URL}: {e}", flush=True)
        return 0


def format_response() -> str:
    """
    Формирует ответ в требуемом формате:
    file content: this text is from file
    env variable: MESSAGE=hello world
    2020-03-30T12:15:17.705Z: 8523ecb1-c716-4cb6-a044-b9e83bb98e43.
    Ping / Pongs: 3
    """
    file_content = read_config_file()
    last_line = read_last_log_line()
    count = fetch_pong_count()

    lines = []

    # Строка 1: содержимое файла из ConfigMap
    lines.append(f"file content: {file_content}")

    # Строка 2: значение env-переменной MESSAGE
    lines.append(f"env variable: MESSAGE={MESSAGE}")

    # Строка 3: последняя строка лога от writer'а
    if not last_line:
        lines.append("No log data available yet.")
    else:
        # Точка в конце строки лога, если её там нет (согласно ТЗ)
        if not last_line.endswith("."):
            last_line = last_line + "."
        lines.append(last_line)

    # Строка 4: количество ping/pong
    lines.append(f"Ping / Pongs: {count}")

    return "\n".join(lines) + "\n"


class LogReaderHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path == "/":
            self._send_text(format_response())

        elif self.path == "/status":
            status = {
                "timestamp": get_timestamp(),
                "log_file": LOG_FILE,
                "config_file": CONFIG_FILE,
                "message": MESSAGE,
                "pingpong_url": PINGPONG_URL,
                "content": format_response(),
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
    print(f"Config file: {CONFIG_FILE}", flush=True)
    print(f"MESSAGE env: {MESSAGE!r}", flush=True)
    print(f"Ping-pong URL: {PINGPONG_URL}", flush=True)

    try:
        # ThreadingHTTPServer вместо HTTPServer для параллельной обработки запросов
        server = ThreadingHTTPServer(("0.0.0.0", PORT), LogReaderHandler)
        server.daemon_threads = True
        server.serve_forever()
    except KeyboardInterrupt:
        print("Reader stopped.", flush=True)


if __name__ == "__main__":
    main()