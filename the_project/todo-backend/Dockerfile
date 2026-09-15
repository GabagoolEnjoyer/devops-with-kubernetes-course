# 1.1
FROM python:3.12-slim

WORKDIR /usr/src/app

# Устанавливаем psycopg v3
RUN pip install --no-cache-dir psycopg[binary]==3.2.3

COPY server.py /usr/src/app/
CMD ["python", "./server.py"]