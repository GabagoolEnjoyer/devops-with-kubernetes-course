#!/usr/bin/env python3
"""
Writer container:
- Генерирует случайную строку при старте
- Каждые 5 секунд дописывает строку с таймстампом в файл
"""

import os
import time
import uuid
from datetime import datetime, timezone

# Путь к общему файлу (будет примонтирован как volume в обоих контейнерах)
LOG_FILE = os.environ.get("LOG_FILE", "/shared/log-output.txt")

# Генерируем случайную строку один раз при старте
RANDOM_STRING = str(uuid.uuid4())


def get_timestamp() -> str:
    now = datetime.now(timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    print(f"Writer started. Random string: {RANDOM_STRING}", flush=True)
    print(f"Writing to file: {LOG_FILE}", flush=True)

    # Создаём директорию, если её нет
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    try:
        while True:
            timestamp = get_timestamp()
            line = f"{timestamp}: {RANDOM_STRING}\n"

            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()

            print(f"Written: {line.strip()}", flush=True)
            time.sleep(5)

    except KeyboardInterrupt:
        print("Writer stopped.", flush=True)


if __name__ == "__main__":
    main()