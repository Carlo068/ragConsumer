"""Creates the database roles the services run as, and gives each one only what it needs.

Before this, the backend, the worker and the MCP server all connected as the
database owner, which can read every password hash and can switch off the audit
log's protections. Now they connect as three limited roles and only the one-shot
`migrate` service holds the owner's password:

  ragapp_backend  the web API: read and write everything except the audit log, which
                  it can only add to and read
  ragapp_mcp      the AI connection: read-only on what it needs to decide who may see
                  what (never password hashes), may stamp an access key's "last used",
                  and may append to the audit log
  ragapp_worker   document indexing: read documents, change their status

Run after every migration (migrate.sh does), because new tables start with no
grants for anyone. Safe to run again: it resets each role's grants and re-applies
them, and sets the passwords from the environment, which is how a password is
rotated.

    DATABASE_URL=<owner url> BACKEND_DB_PASSWORD=... MCP_DB_PASSWORD=... WORKER_DB_PASSWORD=... \
        python scripts/db_roles.py
"""

import os
import re
import sys
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

ROLES = {"backend": "ragapp_backend", "mcp": "ragapp_mcp", "worker": "ragapp_worker"}
PASSWORD_VARS = {"backend": "BACKEND_DB_PASSWORD", "mcp": "MCP_DB_PASSWORD", "worker": "WORKER_DB_PASSWORD"}

APPEND_ONLY = "audit_log"
OWNER_ONLY = {"alembic_version"}  # the migration bookkeeping: no runtime role touches it

# What the MCP server needs: who may see which matter (and nothing about passwords).
MCP_SELECT = ["api_tokens", "ai_matter_selections", "collection_members", "collections", "documents"]
MCP_USER_COLUMNS = ["id", "email", "is_active"]  # NOT password_hash

# What the worker needs: find and claim documents, record their progress.
WORKER_SELECT = ["documents"]
WORKER_COLLECTION_COLUMNS = ["id"]
WORKER_DOCUMENT_UPDATE = ["status", "error_message", "updated_at"]

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def ident(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"unsafe identifier: {name!r}")
    return f'"{name}"'


def grant_statements(kind: str, tables: set[str]) -> list[str]:
    """The GRANT statements for one kind of service, given the tables that exist."""
    role = ident(ROLES[kind])
    statements: list[str] = []

    def need(*names: str) -> None:
        missing = [n for n in names if n not in tables]
        if missing:
            raise RuntimeError(f"expected table(s) not found: {', '.join(missing)} (has the migration run?)")

    if kind == "backend":
        for table in sorted(tables - OWNER_ONLY - {APPEND_ONLY}):
            statements.append(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {ident(table)} TO {role}")
        need(APPEND_ONLY)
        # Read and add only. UPDATE, DELETE and TRUNCATE are never granted, so the
        # log cannot be altered through the application, even if it is compromised.
        statements.append(f"GRANT SELECT, INSERT ON {ident(APPEND_ONLY)} TO {role}")
    elif kind == "mcp":
        need(*MCP_SELECT, "users", APPEND_ONLY)
        for table in MCP_SELECT:
            statements.append(f"GRANT SELECT ON {ident(table)} TO {role}")
        cols = ", ".join(ident(c) for c in MCP_USER_COLUMNS)
        statements.append(f"GRANT SELECT ({cols}) ON {ident('users')} TO {role}")
        statements.append(f"GRANT UPDATE ({ident('last_used_at')}) ON {ident('api_tokens')} TO {role}")
        statements.append(f"GRANT INSERT ON {ident(APPEND_ONLY)} TO {role}")
    elif kind == "worker":
        need(*WORKER_SELECT, "collections")
        for table in WORKER_SELECT:
            statements.append(f"GRANT SELECT ON {ident(table)} TO {role}")
        statements.append(
            f"GRANT SELECT ({', '.join(ident(c) for c in WORKER_COLLECTION_COLUMNS)}) ON {ident('collections')} TO {role}"
        )
        cols = ", ".join(ident(c) for c in WORKER_DOCUMENT_UPDATE)
        statements.append(f"GRANT UPDATE ({cols}) ON {ident('documents')} TO {role}")
    else:
        raise ValueError(kind)
    return statements


def psycopg_url(sqlalchemy_url: str) -> str:
    return make_url(sqlalchemy_url).set(drivername="postgresql").render_as_string(hide_password=False)


def apply_roles(conn: "psycopg.Connection", passwords: dict[str, str]) -> None:
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
    }
    database = conn.execute("SELECT current_database()").fetchone()[0]
    for kind, role_name in ROLES.items():
        password = passwords.get(kind, "")
        if not password:
            raise RuntimeError(f"{PASSWORD_VARS[kind]} is not set")
        role = ident(role_name)
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role_name,)).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(role_name)))
        conn.execute(
            sql.SQL(
                "ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(sql.Identifier(role_name), sql.Literal(password))
        )
        # Start from nothing every time, so a grant that was removed from the lists
        # above is really taken away. (Revoking on a table also revokes its column grants.)
        conn.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}")
        conn.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {role}")
        conn.execute(f"REVOKE ALL ON SCHEMA public FROM {role}")
        conn.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), sql.Identifier(role_name)))
        for statement in grant_statements(kind, tables):
            conn.execute(statement)


def main() -> int:
    owner_url = os.environ.get("DATABASE_URL")
    if not owner_url:
        print("DATABASE_URL (the owner's) is not set", file=sys.stderr)
        return 1
    passwords = {kind: os.environ.get(var, "") for kind, var in PASSWORD_VARS.items()}
    with psycopg.connect(psycopg_url(owner_url)) as conn:
        apply_roles(conn, passwords)
        conn.commit()
    print("Database roles ready: " + ", ".join(ROLES.values()))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.exit(main())
