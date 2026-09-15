# 1.6
FROM python:3.12-slim

WORKDIR /usr/src/app

# Устанавливаем psycopg v3 (новый драйвер)
RUN pip install --no-cache-dir psycopg[binary]==3.2.3

COPY pingpong.py .

CMD ["python", "./pingpong.py"]