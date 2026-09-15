#!/usr/bin/env python3
"""
Ping-pong service (PostgreSQL-backed):
- GET /pingpong — увеличивает счётчик в БД и отвечает "pong N"
- GET /pings    — отдаёт текущее количество pong БЕЗ инкремента
- GET /healthz  — health check (также проверяет доступность БД)
"""

import os
import signal
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock

import psycopg
from psycopg import sql

# ============================================================
# Конфигурация из переменных окружения
# ============================================================
PORT = int(os.environ.get("PORT", "8080"))

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "postgres-practice-0.postgres-practice-svc")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "postgres")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")

DB_STARTUP_RETRIES = int(os.environ.get("DB_STARTUP_RETRIES", "30"))
DB_STARTUP_DELAY = float(os.environ.get("DB_STARTUP_DELAY", "2"))


# ============================================================
# Глобальное состояние соединения с БД
# ============================================================
_db_conn = None
_db_lock = Lock()


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
    """Создаёт таблицу и начальную строку со счётчиком, если их ещё нет."""
    with _db_lock:
        cur = _db_conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pingpong (
                    id INTEGER PRIMARY KEY,
                    count INTEGER NOT NULL
                )
                """
            )
            cur.execute(
                """
                INSERT INTO pingpong (id, count) VALUES (1, 0)
                ON CONFLICT (id) DO NOTHING
                """
            )
        finally:
            cur.close()
    print("✅ Schema initialized (pingpong table)", flush=True)


def get_connection():
    """Возвращает живое соединение, пересоздавая при необходимости."""
    global _db_conn
    with _db_lock:
        if _db_conn is None or _db_conn.closed:
            _db_conn = _connect()
        return _db_conn


def execute_query(query: str, fetchone: bool = False):
    """
    Выполняет SQL-запрос с автоматическим reconnect'ом при обрыве связи.
    """
    for attempt in range(2):
        try:
            conn = get_connection()
            with _db_lock:
                cur = conn.cursor()
                try:
                    cur.execute(query)
                    return cur.fetchone() if fetchone else None
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


# ============================================================
# HTTP-handler
# ============================================================
class PingPongHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path == "/pingpong":
            self._handle_pingpong()
        elif self.path in ("/pings", "/count"):
            self._handle_pings()
        elif self.path == "/healthz":
            self._handle_healthz()
        else:
            self._send_text("Not Found", status=404)

    def _handle_pingpong(self):
        """Атомарный инкремент + возврат нового значения."""
        try:
            row = execute_query(
                "UPDATE pingpong SET count = count + 1 WHERE id = 1 RETURNING count",
                fetchone=True,
            )
            current_count = row[0]
            self._send_text(f"pong {current_count}")
        except Exception as e:
            print(f"ERROR on /pingpong: {e}", flush=True)
            self._send_text("Database error", status=503)

    def _handle_pings(self):
        """Только чтение текущего значения."""
        try:
            row = execute_query(
                "SELECT count FROM pingpong WHERE id = 1",
                fetchone=True,
            )
            current_count = row[0] if row else 0
            self._send_text(str(current_count))
        except Exception as e:
            print(f"ERROR on /pings: {e}", flush=True)
            self._send_text("Database error", status=503)

    def _handle_healthz(self):
        """Health check: приложение живое + БД достижима."""
        try:
            execute_query("SELECT 1", fetchone=True)
            self._send_text("OK")
        except Exception as e:
            self._send_text(f"DB down: {e}", status=503)

    def _send_text(self, text, status=200):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"{self.client_address[0]} - {fmt % args}", flush=True)


# ============================================================
# Entrypoint
# ============================================================
def shutdown(signum, frame):
    print("\nShutting down...", flush=True)
    global _db_conn
    with _db_lock:
        if _db_conn is not None and not _db_conn.closed:
            _db_conn.close()
    sys.exit(0)


def main():
    print(f"Connecting to PostgreSQL at {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}", flush=True)
    wait_for_db()

    global _db_conn
    _db_conn = _connect()
    init_schema()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    server = ThreadingHTTPServer(("0.0.0.0", PORT), PingPongHandler)
    server.daemon_threads = True
    print(f"Ping-pong (PostgreSQL-backed) started on port {PORT}", flush=True)

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