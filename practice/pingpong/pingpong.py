#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Lock
import os

# Путь к файлу на shared volume
COUNTER_FILE = os.environ.get("COUNTER_FILE", "/shared/pingpong-counter.txt")

# Счётчик запросов
counter = 0
counter_lock = Lock()


def load_counter():
    """Загружает счётчик из файла при старте."""
    global counter
    try:
        if os.path.exists(COUNTER_FILE):
            with open(COUNTER_FILE, 'r', encoding='utf-8') as f:
                counter = int(f.read().strip())
                print(f"Loaded counter from file: {counter}", flush=True)
        else:
            counter = 0
            print("Counter file not found, starting from 0", flush=True)
    except (ValueError, IOError) as e:
        counter = 0
        print(f"Error loading counter: {e}, starting from 0", flush=True)


def save_counter():
    """Сохраняет счётчик в файл."""
    try:
        # Создаём директорию, если её нет
        os.makedirs(os.path.dirname(COUNTER_FILE), exist_ok=True)
        
        with open(COUNTER_FILE, 'w', encoding='utf-8') as f:
            f.write(str(counter))
            f.flush()
    except IOError as e:
        print(f"Error saving counter: {e}", flush=True)


class PingPongHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global counter
        
        if self.path == '/pingpong':
            # Увеличиваем счётчик и сохраняем в файл
            with counter_lock:
                counter += 1
                current_count = counter
                save_counter()
            
            response = f"pong {current_count}"
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
        else:
            # Любой другой путь — 404
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Not Found")
    
    def log_message(self, format, *args):
        # Выводим логи в stdout, чтобы их было видно в Kubernetes
        print(f"{self.client_address[0]} - {args[0]}", flush=True)


def main():
    # Загружаем счётчик из файла при старте
    load_counter()
    
    port = 8080
    server = HTTPServer(('', port), PingPongHandler)
    print(f"Ping-pong server started on port {port}", flush=True)
    print(f"Counter file: {COUNTER_FILE}", flush=True)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...", flush=True)
        server.shutdown()


if __name__ == "__main__":
    main()