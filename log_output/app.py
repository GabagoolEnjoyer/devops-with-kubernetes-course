import time
import uuid
from datetime import datetime, timezone


# Генерируем случайную строку один раз при старте
RANDOM_STRING = str(uuid.uuid4())


def get_timestamp() -> str:
    """
    Возвращает текущее UTC-время в формате:
    2020-03-30T12:15:17.705Z
    """
    now = datetime.now(timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    try:
        while True:
            timestamp = get_timestamp()
            print(f"{timestamp}: {RANDOM_STRING}", flush=True)
            time.sleep(5)
    except KeyboardInterrupt:
        # Аккуратный выход по Ctrl+C
        pass


if __name__ == "__main__":
    main()
