#!/usr/bin/env python3
"""
Todo-backend service with PostgreSQL:
- GET  /todos   — отдаёт список всех todo (JSON)
- POST /todos   — создаёт новое todo (JSON-тело {"text": "..."}), отвечает 201
- GET  /healthz — health check (также проверяет доступность БД)

Хранилище — PostgreSQL.
"""

import json
import os
import signal
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import psycopg

DEFAULT_PORT = 8080
MAX_TODO_LEN = 140

# Конфигурация БД из переменных окружения
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "postgres-project-0.postgres-project-svc")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "postgres")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")

DB_STARTUP_RETRIES = int(os.environ.get("DB_STARTUP_RETRIES", "30"))
DB_STARTUP_DELAY = float(os.environ.get("DB_STARTUP_DELAY", "2"))

# Глобальное состояние соединения с БД
_db_conn = None
_db_lock = threading.Lock()


def _conninfo() -> str:
    return (
        f"host={POSTGRES_HOST} "
        f"port={POSTGRES_PORT} "
        f"dbname={POSTGRES_DB} "
        f"user={POSTGRES_USER} "
        f"password={POSTGRES_PASSWORD}"
    )


def _connect():
    """Создаёт новое соединение."""
    conn = psycopg.connect(_conninfo(), autocommit=True)
    return conn


def wait_for_db() -> None:
    """Retry-loop при старте: ждём, пока Postgres примет подключения."""
    for attempt in range(1, DB_STARTUP_RETRIES + 1):
        try:
            conn = _connect()
            conn.close()
            print(f"✅ PostgreSQL is ready (attempt {attempt})", flush=True)
            return
        except psycopg.OperationalError as e:
            print(
                f"⏳ Waiting for PostgreSQL (attempt {attempt}/{DB_STARTUP_RETRIES}): {e}",
                flush=True,
            )
            time.sleep(DB_STARTUP_DELAY)

    print("❌ Failed to connect to PostgreSQL after all retries, exiting.", flush=True)
    sys.exit(1)


def init_schema() -> None:
    """Создаёт таблицу todos, если её ещё нет."""
    with _db_lock:
        cur = _db_conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS todos (
                    id SERIAL PRIMARY KEY,
                    text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )
        finally:
            cur.close()
    print("✅ Schema initialized (todos table)", flush=True)


def get_connection():
    """Возвращает живое соединение, пересоздавая при необходимости."""
    global _db_conn
    with _db_lock:
        if _db_conn is None or _db_conn.closed:
            _db_conn = _connect()
        return _db_conn


def execute_query(query: str, params: tuple = None, fetchone: bool = False, fetchall: bool = False):
    """
    Выполняет SQL-запрос с автоматическим reconnect'ом при обрыве связи.
    """
    for attempt in range(2):
        try:
            conn = get_connection()
            with _db_lock:
                cur = conn.cursor()
                try:
                    cur.execute(query, params)
                    if fetchone:
                        return cur.fetchone()
                    elif fetchall:
                        return cur.fetchall()
                    return None
                finally:
                    cur.close()
        except (psycopg.OperationalError, psycopg.InterfaceError) as e:
            print(f"⚠️  DB error (attempt {attempt + 1}): {e}", flush=True)
            with _db_lock:
                global _db_conn
                try:
                    if _db_conn is not None and not _db_conn.closed:
                        _db_conn.close()
                except Exception:
                    pass
                _db_conn = None
            time.sleep(0.5)

    raise RuntimeError("Database unavailable after reconnect attempt")


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

    def _cors_headers(self):
        """CORS заголовки для доступа с других портов при локальной разработке."""
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

    def do_OPTIONS(self):
        """CORS preflight от браузера."""
        self.send_response(204)
        self._cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/todos":
            self._handle_get_todos()
        elif path == "/healthz":
            self._handle_healthz()
        else:
            self._send_json({"error": "Not Found"}, status=404)

    def _handle_get_todos(self):
        """Отдаёт список всех todo из БД."""
        try:
            rows = execute_query(
                "SELECT id, text, created_at FROM todos ORDER BY id",
                fetchall=True,
            )
            todos = [
                {"id": row[0], "text": row[1], "created_at": row[2].isoformat()}
                for row in rows
            ]
            self._send_json(todos)
        except Exception as e:
            print(f"ERROR on GET /todos: {e}", flush=True)
            self._send_json({"error": "Database error"}, status=503)

    def _handle_healthz(self):
        """Health check: приложение живое + БД достижима."""
        try:
            execute_query("SELECT 1", fetchone=True)
            self._send_json({"status": "OK"})
        except Exception as e:
            self._send_json({"status": "DB down", "error": str(e)}, status=503)

    def do_POST(self):
        path = urlparse(self.path).path

        if path != "/todos":
            self._send_json({"error": "Not Found"}, status=404)
            return

        self._handle_create_todo()

    def _handle_create_todo(self):
        """Создаёт новый todo в БД."""
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

        try:
            row = execute_query(
                "INSERT INTO todos (text) VALUES (%s) RETURNING id, text, created_at",
                params=(text,),
                fetchone=True,
            )
            todo = {
                "id": row[0],
                "text": row[1],
                "created_at": row[2].isoformat()
            }
            print(f"Created todo #{todo['id']}: {todo['text']}", flush=True)
            self._send_json(todo, status=201)
        except Exception as e:
            print(f"ERROR on POST /todos: {e}", flush=True)
            self._send_json({"error": "Database error"}, status=503)

    def do_HEAD(self):
        self.do_GET()

    def log_message(self, fmt, *args):
        print(f"{self.client_address[0]} - {fmt % args}", flush=True)


def shutdown(signum, frame):
    """Graceful shutdown: закрываем соединение с БД."""
    print("\nShutting down...", flush=True)
    global _db_conn
    with _db_lock:
        if _db_conn is not None and not _db_conn.closed:
            _db_conn.close()
    sys.exit(0)


def main():
    port = get_port()

    print(f"Connecting to PostgreSQL at {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}", flush=True)
    wait_for_db()

    global _db_conn
    _db_conn = _connect()
    init_schema()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), TodoBackendHandler)
    except OSError as exc:
        print(
            f"ERROR: cannot bind to port {port}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    server.daemon_threads = True

    print(f"Todo-backend (PostgreSQL) started on port {port}", flush=True)

    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        server.server_close()
        if _db_conn and not _db_conn.closed:
            _db_conn.close()


if __name__ == "__main__":
    main()