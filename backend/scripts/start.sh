#!/bin/sh
# Container start for the API. Migrations and database roles are handled by the
# one-shot "migrate" service (scripts/migrate.sh), which holds the owner credentials;
# this process only ever has the limited backend role.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
