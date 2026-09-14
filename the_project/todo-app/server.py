#!/usr/bin/env python3
"""Minimal Todo App HTTP server with cached random bear image.

Server-side rendering: список todo запрашивается у todo-backend
изнутри кластера и встраивается в HTML на момент запроса страницы.
"""

import json
import os
import random
import signal
import sys
import threading
import time
import urllib.request
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_PORT = 3000
BASE_DIR = Path(__file__).parent
INDEX_HTML_PATH = BASE_DIR / "index.html"

# Внутренний адрес todo-backend: по нему ходит САМ todo-app (GET /todos).
# Браузер его не видит — это server-to-server запрос внутри кластера.
TODOS_URL = os.environ.get("TODOS_URL", "http://todo-backend-service:8888")

# Адрес, по которому БРАУЗЕР постит новые todo (маршрутизирует Ingress).
TODOS_POST_URL = os.environ.get("TODOS_POST_URL", "/todos")

# Таймаут запросов к todo-backend, чтобы не подвешивать отдачу страницы
TODOS_TIMEOUT = float(os.environ.get("TODOS_TIMEOUT", "3"))

# Директория для кеша картинки (должна указывать на примонтированный том)
CACHE_DIR = Path(os.environ.get("CACHE_DIR", str(BASE_DIR / "files")))
IMAGE_PATH = CACHE_DIR / "bear.jpg"
META_PATH = CACHE_DIR / "bear-meta.json"

# Сколько секунд картинка считается "свежей" (10 минут)
CACHE_TTL = int(os.environ.get("CACHE_TTL", "600"))

# Диапазон случайных размеров для placebear
MIN_SIZE = 500
MAX_SIZE = 700

# Блокировка, чтобы два одновременных запроса не качали картинку дважды
_image_lock = threading.Lock()


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


def fetch_todos() -> list:
    """Server-side запрос списка todo у todo-backend (внутри кластера)."""
    url = TODOS_URL.rstrip("/") + "/todos"

    try:
        with urllib.request.urlopen(url, timeout=TODOS_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError) as exc:
        print(f"Warning: cannot fetch todos from {url}: {exc}", flush=True)
        return []


def render_todo_items(todos: list) -> str:
    """Превращает список todo в готовые <li> для HTML (с экранированием)."""
    if not todos:
        return "<li>No todos yet — add the first one!</li>"

    items = []
    for todo in todos:
        text = todo.get("text", "") if isinstance(todo, dict) else str(todo)
        items.append(f"<li>{escape(text)}</li>")

    return "\n            ".join(items)


def random_bear_url() -> str:
    """Генерирует случайный URL вида https://placebear.com/x/y."""
    width = random.randint(MIN_SIZE, MAX_SIZE)
    height = random.randint(MIN_SIZE, MAX_SIZE)
    return f"https://placebear.com/{width}/{height}"


def load_meta() -> dict:
    """Читает метаданные кеша (время загрузки, флаг 'старую уже показали')."""
    try:
        with META_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_meta(meta: dict) -> None:
    """Атомарно сохраняет метаданные кеша."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = META_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(meta, f)
    os.replace(tmp, META_PATH)


def fetch_new_image() -> bool:
    """Качает новую случайную картинку и атомарно кладёт её в кеш."""
    url = random_bear_url()
    print(f"Fetching new bear image from {url}", flush=True)

    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = resp.read()
    except Exception as exc:
        print(f"ERROR: failed to fetch image: {exc}", flush=True)
        return False

    if not data:
        print("ERROR: empty response from image API", flush=True)
        return False

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = IMAGE_PATH.with_suffix(".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, IMAGE_PATH)  # атомарная замена, без битых файлов

    save_meta({
        "fetched_at": time.time(),
        "url": url,
        "stale_served": False,
    })
    print(f"Cached new image ({len(data)} bytes) from {url}", flush=True)
    return True


def ensure_image() -> None:
    """
    Гарантирует, что в IMAGE_PATH лежит та картинка, которую нужно отдать:
    - кеша нет            -> качаем новую
    - кеш свежий (<10 мин) -> отдаём как есть
    - кеш протух, старую ещё не показывали -> показываем старую последний раз
    - кеш протух, старую уже показали       -> качаем новую
    """
    with _image_lock:
        meta = load_meta()
        has_image = IMAGE_PATH.exists() and IMAGE_PATH.stat().st_size > 0

        if not has_image or not meta:
            fetch_new_image()
            return

        age = time.time() - meta.get("fetched_at", 0)

        if age < CACHE_TTL:
            return  # кеш ещё свежий

        if not meta.get("stale_served"):
            # Даём старой картинке последний шанс
            meta["stale_served"] = True
            save_meta(meta)
            print("Cache expired: serving stale image one more time", flush=True)
            return

        fetch_new_image()


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

    def _send_image(self, data: bytes, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(data)))
        # Чтобы браузер не кешировал картинку сам и всегда спрашивал сервер
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        if self.command != "HEAD":
            self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        port = self.server.server_address[1]

        if path == "/":
            try:
                template = INDEX_HTML_PATH.read_text(encoding="utf-8")
                html = (
                    template
                    .replace("{port}", str(port))
                    .replace("{todo_items}", render_todo_items(fetch_todos()))
                    .replace("{todos_post_url}", TODOS_POST_URL)
                )
            except FileNotFoundError:
                html = "<h1>index.html not found</h1>"
            self._send_html(html)

        elif path in ("/image", "/bear.jpg"):
            ensure_image()
            try:
                data = IMAGE_PATH.read_bytes()
            except OSError:
                self._send_text("Image not available", status=503)
                return
            self._send_image(data)

        elif path == "/healthz":
            self._send_text("OK")

        elif path == "/shutdown":
            # Тестовый эндпоинт: имитирует падение контейнера
            self._send_text("Shutting down for test...\n")
            threading.Timer(0.5, lambda: os._exit(0)).start()

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
    print(f"Image cache dir: {CACHE_DIR}", flush=True)
    print(f"Cache TTL: {CACHE_TTL}s", flush=True)
    print(f"Todos backend (server-side): {TODOS_URL}", flush=True)
    print(f"Todos POST url (browser): {TODOS_POST_URL}", flush=True)

    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()