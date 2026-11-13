"""The shape of the database grants (the live behaviour is proven against a real
Postgres by scripts/check_db_roles.py, which run-checks --stack runs)."""

import pytest

from scripts.db_roles import ROLES, grant_statements, ident

TABLES = {
    "users", "collections", "collection_members", "documents", "invites", "api_tokens",
    "ai_matter_selections", "audit_log", "user_sessions", "alembic_version",
}


def all_statements(kind):
    return grant_statements(kind, TABLES)


@pytest.mark.parametrize("kind", ROLES)
def test_no_role_can_change_or_remove_audit_entries(kind):
    for statement in all_statements(kind):
        if '"audit_log"' in statement:
            privileges = statement.split(" ON ")[0].replace("GRANT ", "")
            assert "UPDATE" not in privileges and "DELETE" not in privileges and "TRUNCATE" not in privileges
            assert "ALL" not in privileges.split(", ")


def test_the_backend_may_read_and_append_to_the_audit_log_and_nothing_else_there():
    statements = [s for s in all_statements("backend") if '"audit_log"' in s]
    assert statements == ['GRANT SELECT, INSERT ON "audit_log" TO "ragapp_backend"']


def test_the_backend_gets_every_other_table_but_not_the_migration_bookkeeping():
    text = "\n".join(all_statements("backend"))
    for table in TABLES - {"audit_log", "alembic_version"}:
        assert f'ON "{table}" TO' in text
    assert "alembic_version" not in text


def test_a_new_table_is_covered_for_the_backend_automatically_but_not_for_the_others():
    tables = TABLES | {"brand_new"}
    assert any('"brand_new"' in s for s in grant_statements("backend", tables))
    assert not any('"brand_new"' in s for s in grant_statements("mcp", tables))
    assert not any('"brand_new"' in s for s in grant_statements("worker", tables))


def test_the_mcp_role_never_reads_password_hashes_or_changes_users():
    text = "\n".join(all_statements("mcp"))
    assert 'password_hash' not in text
    assert 'SELECT ("id", "email", "is_active") ON "users"' in text
    for statement in all_statements("mcp"):
        if 'ON "users"' in statement:
            assert statement.startswith("GRANT SELECT (")
    assert 'GRANT UPDATE ("last_used_at") ON "api_tokens"' in text
    assert 'GRANT INSERT ON "audit_log"' in text
    # it can read the log?  No: insert only.
    assert 'GRANT SELECT ON "audit_log"' not in text


def test_the_mcp_role_gets_exactly_these_whole_table_reads():
    reads = {s.split(" ON ")[1].split(" TO ")[0] for s in all_statements("mcp") if s.startswith("GRANT SELECT ON")}
    assert reads == {'"api_tokens"', '"ai_matter_selections"', '"collection_members"', '"collections"', '"documents"'}


def test_the_worker_role_is_limited_to_documents_progress():
    statements = all_statements("worker")
    assert 'GRANT SELECT ON "documents" TO "ragapp_worker"' in statements
    assert 'GRANT UPDATE ("status", "error_message", "updated_at") ON "documents" TO "ragapp_worker"' in statements
    assert 'GRANT SELECT ("id") ON "collections" TO "ragapp_worker"' in statements
    assert not any("users" in s or "audit_log" in s for s in statements)
    assert not any(s.startswith("GRANT INSERT") or s.startswith("GRANT DELETE") for s in statements)


def test_a_missing_table_is_an_error_not_a_silent_gap():
    with pytest.raises(RuntimeError, match="not found"):
        grant_statements("mcp", TABLES - {"api_tokens"})
    with pytest.raises(RuntimeError, match="not found"):
        grant_statements("backend", TABLES - {"audit_log"})


def test_identifiers_are_validated():
    assert ident("audit_log") == '"audit_log"'
    for bad in ('x"; DROP TABLE users; --', "Users", "a b", ""):
        with pytest.raises(ValueError):
            ident(bad)
