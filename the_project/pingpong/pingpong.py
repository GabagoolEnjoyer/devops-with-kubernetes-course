from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Lock


# Счётчик запросов в памяти
counter = 0
counter_lock = Lock()


class PingPongHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global counter
        
        if self.path == '/pingpong':
            # Увеличиваем счётчик
            with counter_lock:
                counter += 1
                current_count = counter
            
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
    port = 8080
    server = HTTPServer(('', port), PingPongHandler)
    print(f"Ping-pong server started on port {port}", flush=True)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...", flush=True)
        server.shutdown()


if __name__ == "__main__":
    main()