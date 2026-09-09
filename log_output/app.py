import time
import uuid
import json
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread


# Генерируем случайную строку один раз при старте
RANDOM_STRING = str(uuid.uuid4())


def get_timestamp() -> str:
    """
    Возвращает текущее UTC-время в формате:
    2020-03-30T12:15:17.705Z
    """
    now = datetime.now(timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/status':
            status = {
                "timestamp": get_timestamp(),
                "random_string": RANDOM_STRING
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(status).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Отключаем стандартное логирование HTTP-запросов
        pass


def start_http_server(port=8080):
    server = HTTPServer(('', port), StatusHandler)
    thread = Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    print(f"HTTP server started on port {port}", flush=True)


def main() -> None:
    try:
        # Запускаем HTTP-сервер в отдельном потоке
        start_http_server()
        
        while True:
            timestamp = get_timestamp()
            print(f"{timestamp}: {RANDOM_STRING}", flush=True)
            time.sleep(5)
    except KeyboardInterrupt:
        # Аккуратный выход по Ctrl+C
        pass


if __name__ == "__main__":
    main()