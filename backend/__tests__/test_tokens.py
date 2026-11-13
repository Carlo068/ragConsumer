from datetime import timedelta

from sqlalchemy import select

from app.config import settings
from app.models import ApiToken
from app.routers.admin import utcnow
from app.routers.tokens import hash_token


def test_create_returns_raw_token_once_and_stores_only_hash(logged_in_client, db):
    client, user = logged_in_client
    response = client.post("/tokens", json={"name": "Claude Desktop"})
    assert response.status_code == 201
    body = response.json()
    assert body["token"].startswith("rag_")
    assert body["prefix"] == body["token"][:8]

    stored = db.scalars(select(ApiToken)).one()
    assert stored.user_id == user.id
    assert stored.token_hash == hash_token(body["token"])
    assert body["token"] not in (stored.token_hash, stored.prefix, stored.name)

    # The list never exposes the secret.
    listed = client.get("/tokens").json()
    assert len(listed) == 1
    assert "token" not in listed[0] and "token_hash" not in listed[0]


def test_token_expires_after_configured_days(logged_in_client, db):
    client, _ = logged_in_client
    client.post("/tokens", json={"name": "x"})
    stored = db.scalars(select(ApiToken)).one()
    expected = utcnow() + timedelta(days=settings.TOKEN_TTL_DAYS)
    assert abs((stored.expires_at - expected).total_seconds()) < 60


def test_requires_login(client):
    assert client.get("/tokens").status_code == 401
    assert client.post("/tokens", json={"name": "x"}).status_code == 401


def test_users_only_see_and_revoke_their_own_tokens(client, make_user, db):
    make_user("a@firm.mx")
    make_user("b@firm.mx")
    client.post("/auth/login", json={"email": "a@firm.mx", "password": "password123"})
    token_id = client.post("/tokens", json={"name": "a's"}).json()["id"]

    client.post("/auth/logout")
    client.post("/auth/login", json={"email": "b@firm.mx", "password": "password123"})
    assert client.get("/tokens").json() == []
    assert client.delete(f"/tokens/{token_id}").status_code == 404
    assert db.scalars(select(ApiToken)).one().revoked_at is None


def test_revoke_marks_token_and_hides_it(logged_in_client, db):
    client, _ = logged_in_client
    token_id = client.post("/tokens", json={"name": "x"}).json()["id"]
    assert client.delete(f"/tokens/{token_id}").status_code == 204
    assert client.get("/tokens").json() == []
    assert db.scalars(select(ApiToken)).one().revoked_at is not None
    # Revoking twice behaves like a missing token.
    assert client.delete(f"/tokens/{token_id}").status_code == 404


def test_active_token_limit(logged_in_client, monkeypatch):
    client, _ = logged_in_client
    monkeypatch.setattr(settings, "MAX_ACTIVE_TOKENS_PER_USER", 2)
    assert client.post("/tokens", json={"name": "1"}).status_code == 201
    second = client.post("/tokens", json={"name": "2"}).json()
    assert client.post("/tokens", json={"name": "3"}).status_code == 409
    # Revoking frees a slot.
    client.delete(f"/tokens/{second['id']}")
    assert client.post("/tokens", json={"name": "3"}).status_code == 201


def test_name_is_required(logged_in_client):
    client, _ = logged_in_client
    assert client.post("/tokens", json={"name": ""}).status_code == 422
