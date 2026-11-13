from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.tokens import find_token_owner, hash_token

NOW = datetime(2026, 11, 13, 12, 0, 0)


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE api_tokens (id TEXT PRIMARY KEY, user_id TEXT, token_hash TEXT, "
                "expires_at TIMESTAMP, last_used_at TIMESTAMP, revoked_at TIMESTAMP)"
            )
        )
    return engine


def add_token(engine, raw="rag_secret", *, expires=NOW + timedelta(days=1), revoked=None):
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO api_tokens (id, user_id, token_hash, expires_at, revoked_at) "
                "VALUES ('t1', 'u1', :h, :e, :r)"
            ),
            {"h": hash_token(raw), "e": expires, "r": revoked},
        )


def test_hash_matches_what_the_backend_stores():
    # sha256("abc") -- the backend hashes the same way (backend/app/routers/tokens.py).
    assert hash_token("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_a_valid_token_resolves_to_its_owner(engine):
    add_token(engine)
    owner = find_token_owner(engine, "rag_secret", now=NOW)
    assert owner is not None and owner.user_id == "u1" and owner.token_id == "t1"


def test_use_is_recorded(engine):
    add_token(engine)
    find_token_owner(engine, "rag_secret", now=NOW)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT last_used_at FROM api_tokens")).scalar() is not None


@pytest.mark.parametrize("presented", ["", "rag_other", "rag_secre", "RAG_SECRET"])
def test_unknown_tokens_are_rejected(engine, presented):
    add_token(engine)
    assert find_token_owner(engine, presented, now=NOW) is None


def test_a_revoked_token_is_rejected(engine):
    add_token(engine, revoked=NOW - timedelta(hours=1))
    assert find_token_owner(engine, "rag_secret", now=NOW) is None


def test_an_expired_token_is_rejected(engine):
    add_token(engine, expires=NOW - timedelta(seconds=1))
    assert find_token_owner(engine, "rag_secret", now=NOW) is None


def test_a_rejected_token_is_not_stamped_as_used(engine):
    add_token(engine, revoked=NOW - timedelta(hours=1))
    find_token_owner(engine, "rag_secret", now=NOW)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT last_used_at FROM api_tokens")).scalar() is None
