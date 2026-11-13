#!/bin/sh
# Runs once per start of the stack, as the database OWNER, before any service starts:
# brings the schema up to date, then (re)creates the limited roles the services use.
# If the upgrade fails ONLY because the database is newer than this code (after a
# rollback), carry on; any other failure stops here and nothing starts.
if ! alembic upgrade head; then
  python scripts/db_ahead.py || exit 1
fi
exec python scripts/db_roles.py
