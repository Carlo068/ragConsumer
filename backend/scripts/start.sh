#!/bin/sh
# Container start: bring the database up to date, then run the API.
# If the upgrade fails ONLY because the database is newer than this code (after
# a rollback), start anyway; any other failure stops the container.
if ! alembic upgrade head; then
  python scripts/db_ahead.py || exit 1
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
