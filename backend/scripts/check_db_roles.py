"""Proves, against the running database, that each service's role can do what it
needs and is REFUSED everything else, including switching off the audit log's
protections. Every statement runs in a transaction that is rolled back, so
nothing changes.

Run it where the owner's URL and the three role passwords are available, which is
the one-shot `migrate` service:

    docker compose run --rm --no-deps --entrypoint python migrate scripts/check_db_roles.py

(run-checks --stack does this.) Exit status 0 only if every check passes.
"""

import os
import sys

import psycopg
from psycopg import errors
from sqlalchemy.engine import make_url

from db_roles import PASSWORD_VARS, ROLES, psycopg_url

OWNER_URL = os.environ["DATABASE_URL"]
ROW = "gen_random_uuid()"  # a throwaway id for inserts that are rolled back

fails = 0


def connect(kind: str) -> "psycopg.Connection":
    url = make_url(OWNER_URL).set(drivername="postgresql", username=ROLES[kind], password=os.environ[PASSWORD_VARS[kind]])
    return psycopg.connect(url.render_as_string(hide_password=False))


def report(ok: bool, what: str, detail: str = "") -> None:
    global fails
    print(("  PASS  " if ok else "  FAIL  ") + what + ("" if ok else f"  ({detail})"))
    fails += 0 if ok else 1


def allowed(kind: str, sql: str, what: str) -> None:
    with connect(kind) as conn:
        try:
            conn.execute(sql)
            report(True, f"{kind} may {what}")
        except psycopg.Error as exc:
            report(False, f"{kind} may {what}", f"{type(exc).__name__}: {exc}".splitlines()[0])
        finally:
            conn.rollback()


def refused(kind: str, sql: str, what: str) -> None:
    """Passes only when Postgres says 'permission denied' (42501): a different
    error would mean the test statement was wrong, not that the role is safe."""
    with connect(kind) as conn:
        try:
            conn.execute(sql)
            report(False, f"{kind} is refused: {what}", "it was ALLOWED")
        except errors.InsufficientPrivilege:
            report(True, f"{kind} is refused: {what}")
        except psycopg.Error as exc:
            report(False, f"{kind} is refused: {what}", f"failed for another reason: {type(exc).__name__}: {exc}".splitlines()[0])
        finally:
            conn.rollback()


print("Backend role (the web API)")
allowed("backend", "SELECT id, email, password_hash FROM users LIMIT 1", "read users (it signs people in)")
allowed("backend", "UPDATE users SET is_admin = is_admin WHERE false", "update users")
allowed("backend", "DELETE FROM documents WHERE false", "delete documents")
allowed("backend", "SELECT * FROM audit_log LIMIT 1", "read the audit log")
allowed("backend", f"INSERT INTO audit_log (id, action) VALUES ({ROW}, 'role_check')", "add to the audit log")
refused("backend", "UPDATE audit_log SET action = 'x'", "edit the audit log")
refused("backend", "DELETE FROM audit_log", "delete from the audit log")
refused("backend", "TRUNCATE audit_log", "empty the audit log")
refused("backend", "ALTER TABLE audit_log DISABLE TRIGGER ALL", "switch off the audit log's triggers")
refused("backend", "ALTER TABLE audit_log DROP COLUMN action", "alter the audit log's structure")
refused("backend", "ALTER TABLE users DISABLE TRIGGER ALL", "switch off triggers on any table")
refused("backend", "DROP TABLE documents", "drop a table")
refused("backend", "CREATE TABLE public.zz_role_check (a int)", "create a table")
refused("backend", "CREATE ROLE zz_role_check", "create a role")
refused("backend", "SET session_replication_role = replica", "turn off all triggers for its session")
refused("backend", "SELECT * FROM alembic_version", "read the migration bookkeeping")
refused("backend", "ALTER ROLE ragapp_backend SUPERUSER", "make itself a superuser")

print("MCP role (the AI connection)")
allowed("mcp", "SELECT id, user_id, token_hash, expires_at, revoked_at FROM api_tokens LIMIT 1", "read access keys")
allowed("mcp", "SELECT id, email, is_active FROM users LIMIT 1", "read who a person is and whether they are active")
for table in ("ai_matter_selections", "collection_members", "collections", "documents"):
    allowed("mcp", f"SELECT * FROM {table} LIMIT 1", f"read {table}")
allowed("mcp", "UPDATE api_tokens SET last_used_at = now() WHERE false", "stamp a key's last use")
allowed("mcp", f"INSERT INTO audit_log (id, action) VALUES ({ROW}, 'role_check')", "add to the audit log")
refused("mcp", "SELECT password_hash FROM users LIMIT 1", "read password hashes")
refused("mcp", "SELECT * FROM users LIMIT 1", "read the whole users table")
refused("mcp", "UPDATE users SET is_admin = true", "change a user")
refused("mcp", "UPDATE api_tokens SET revoked_at = now()", "change anything about a key except its last use")
refused("mcp", "DELETE FROM api_tokens", "delete keys")
refused("mcp", "UPDATE documents SET status = 'ready'", "change documents")
refused("mcp", "DELETE FROM collection_members", "change who belongs to a matter")
refused("mcp", "SELECT * FROM audit_log LIMIT 1", "read the audit log")
refused("mcp", "UPDATE audit_log SET action = 'x'", "edit the audit log")
refused("mcp", "DELETE FROM audit_log", "delete from the audit log")
refused("mcp", "ALTER TABLE audit_log DISABLE TRIGGER ALL", "switch off the audit log's triggers")
refused("mcp", "SELECT * FROM user_sessions LIMIT 1", "read sign-in sessions")
refused("mcp", "SELECT * FROM invites LIMIT 1", "read invitations")

print("Worker role (document indexing)")
allowed("worker", "SELECT id, collection_id, object_key, source_filename, status, created_at FROM documents LIMIT 1", "read documents")
allowed("worker", "UPDATE documents SET status = status, error_message = error_message, updated_at = now() WHERE false", "record a document's progress")
allowed("worker", "SELECT 1 FROM collections WHERE id IS NOT NULL LIMIT 1", "check that a matter exists")
refused("worker", "SELECT password_hash FROM users LIMIT 1", "read password hashes")
refused("worker", "SELECT * FROM users LIMIT 1", "read users")
refused("worker", "SELECT name FROM collections LIMIT 1", "read matter names")
refused("worker", "UPDATE documents SET source_filename = 'x'", "change a document's name")
refused("worker", "DELETE FROM documents", "delete documents")
refused("worker", "UPDATE users SET is_admin = true", "change a user")
refused("worker", "SELECT * FROM audit_log LIMIT 1", "read the audit log")
refused("worker", f"INSERT INTO audit_log (id, action) VALUES ({ROW}, 'x')", "write to the audit log")
refused("worker", "ALTER TABLE audit_log DISABLE TRIGGER ALL", "switch off the audit log's triggers")

print("The roles and the audit log's own protection")
with psycopg.connect(psycopg_url(OWNER_URL)) as owner:
    rows = owner.execute(
        "SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolreplication FROM pg_roles WHERE rolname = ANY(%s)",
        (list(ROLES.values()),),
    ).fetchall()
    report(len(rows) == 3, "all three roles exist", str(rows))
    report(all(not any(r[1:]) for r in rows), "none is a superuser, can create roles or databases, bypass row security or replicate")
    triggers = owner.execute(
        "SELECT tgname, tgenabled FROM pg_trigger WHERE tgrelid = 'audit_log'::regclass AND NOT tgisinternal"
    ).fetchall()
    report(len(triggers) >= 1 and all(t[1] == "O" for t in triggers), "the audit log's triggers are in place and enabled", str(triggers))

print("\nDATABASE ROLES " + ("OK" if fails == 0 else "FAILED"))
sys.exit(1 if fails else 0)
