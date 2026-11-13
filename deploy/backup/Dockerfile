# Backup and restore tool. Based on the same Postgres major version as the
# database so pg_dump / pg_restore always match it. Runs only on demand
# (`docker compose --profile tools run --rm backup ...`), never as a server.
FROM postgres:16
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 age rclone curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY backup.py retention.py /app/
WORKDIR /app
ENTRYPOINT ["python3", "/app/backup.py"]
