"""Disabling people, ending sessions, changing and resetting passwords, and
pausing sign-in after repeated failures (KAN-96)."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app import audit
from app.config import settings
from app.main import app
from app.models import ApiToken, AuditLog, User, UserSession
from app.ratelimit import RateLimiter
from app.routers import invites as invites_module
from app.routers.admin import utcnow


def entries(db, action):
    db.expire_all()
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)))


def login(client, email, password="password123"):
    return client.post("/auth/login", json={"email": email, "password": password})


@pytest.fixture
def second_browser():
    """A separate cookie jar: the same person on another device."""
    with TestClient(app) as other:
        yield other


@pytest.fixture
def third_browser():
    with TestClient(app) as other:
        yield other


@pytest.fixture(autouse=True)
def fresh_invite_limiter(monkeypatch):
    monkeypatch.setattr(invites_module, "_limiter", RateLimiter(1000, 60))


# --- sessions live on the server --------------------------------------------------

def test_signing_out_ends_the_session_even_for_a_copied_cookie(logged_in_client):
    client, _ = logged_in_client
    copied = client.cookies.get("session")
    assert client.get("/auth/me").status_code == 200

    client.post("/auth/logout")

    client.cookies.set("session", copied)
    assert client.get("/auth/me").status_code == 401


def test_the_cookie_is_http_only_and_same_site_lax(client, make_user):
    make_user()
    header = login(client, "alice@example.com").headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=lax" in header


def test_a_session_ends_after_the_idle_time(logged_in_client, db):
    client, _ = logged_in_client
    assert client.get("/auth/me").status_code == 200

    db.execute(update(UserSession).values(last_seen_at=utcnow() - timedelta(minutes=settings.SESSION_IDLE_MINUTES + 1)))
    db.commit()

    assert client.get("/auth/me").status_code == 401
    # and it stays ended
    assert client.get("/auth/me").status_code == 401


def test_activity_keeps_a_session_alive(logged_in_client, db):
    client, _ = logged_in_client
    db.execute(update(UserSession).values(last_seen_at=utcnow() - timedelta(minutes=settings.SESSION_IDLE_MINUTES - 5)))
    db.commit()

    assert client.get("/auth/me").status_code == 200
    db.expire_all()
    seen = db.scalars(select(UserSession)).one().last_seen_at
    assert utcnow() - seen < timedelta(minutes=1)


# --- an administrator disables an account ------------------------------------------

def test_disabling_a_user_ends_their_sessions_and_keys_immediately(admin_client, make_user, second_browser, db):
    admin, _ = admin_client
    user = make_user(email="leaving@firm.mx")
    login(second_browser, "leaving@firm.mx")
    key = second_browser.post("/tokens", json={"name": "laptop"}).json()["token"]
    assert second_browser.get("/auth/me").status_code == 200

    response = admin.post(f"/admin/users/{user.id}/disable")

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert second_browser.get("/auth/me").status_code == 401, "the open session must stop at once"
    db.expire_all()
    assert db.scalars(select(ApiToken)).one().revoked_at is not None, "AI keys are revoked"
    assert key  # (the key itself is checked against the MCP server in its own tests)

    entry = entries(db, audit.USER_DISABLED)[0]
    assert entry.target == "leaving@firm.mx"
    assert entry.detail == {"sessions_ended": 1, "tokens_revoked": 1}


def test_a_disabled_user_cannot_sign_in_and_is_told_nothing_extra(admin_client, make_user, second_browser, db):
    admin, _ = admin_client
    user = make_user(email="leaving@firm.mx")
    admin.post(f"/admin/users/{user.id}/disable")

    right = login(second_browser, "leaving@firm.mx")
    wrong = login(second_browser, "leaving@firm.mx", "not the password")

    assert right.status_code == wrong.status_code == 401
    assert right.json()["code"] == wrong.json()["code"] == "invalid_credentials"
    reasons = [e.detail for e in entries(db, audit.LOGIN_FAILED)]
    assert {"reason": "account_disabled"} in reasons, "the administrator can see why in the log"


def test_enabling_restores_sign_in_but_not_the_old_keys(admin_client, make_user, second_browser, db):
    admin, _ = admin_client
    user = make_user(email="back@firm.mx")
    login(second_browser, "back@firm.mx")
    second_browser.post("/tokens", json={"name": "k"})
    admin.post(f"/admin/users/{user.id}/disable")

    assert login(second_browser, "back@firm.mx").status_code == 401
    assert admin.post(f"/admin/users/{user.id}/enable").json()["is_active"] is True
    assert login(second_browser, "back@firm.mx").status_code == 200
    db.expire_all()
    assert db.scalars(select(ApiToken)).one().revoked_at is not None
    assert entries(db, audit.USER_ENABLED)


def test_an_administrator_cannot_disable_themselves(admin_client):
    admin, me = admin_client
    response = admin.post(f"/admin/users/{me.id}/disable")
    assert response.status_code == 409
    assert response.json()["code"] == "cannot_disable_self"
    assert admin.get("/auth/me").status_code == 200


def test_only_administrators_manage_users(logged_in_client, make_user):
    client, _ = logged_in_client
    other = make_user(email="other@firm.mx")
    for path in ("disable", "enable", "end-sessions", "password-reset"):
        response = client.post(f"/admin/users/{other.id}/{path}")
        assert response.status_code == 403, path
        assert response.json()["code"] == "admin_required"


def test_unknown_user_is_not_found(admin_client):
    admin, _ = admin_client
    response = admin.post("/admin/users/00000000-0000-0000-0000-000000000000/disable")
    assert response.status_code == 404
    assert response.json()["code"] == "user_not_found"


def test_ending_sessions_signs_the_person_out_everywhere_but_only_them(admin_client, make_user, second_browser, third_browser, db):
    admin, _ = admin_client
    target = make_user(email="target@firm.mx")
    bystander = make_user(email="bystander@firm.mx")
    login(second_browser, "target@firm.mx")
    login(third_browser, "bystander@firm.mx")

    assert admin.post(f"/admin/users/{target.id}/end-sessions").status_code == 204

    assert second_browser.get("/auth/me").status_code == 401
    assert third_browser.get("/auth/me").status_code == 200
    assert login(second_browser, "target@firm.mx").status_code == 200, "ending sessions does not disable the account"
    assert entries(db, audit.SESSIONS_ENDED)[0].target == "target@firm.mx"


def test_the_user_list_says_who_is_disabled(admin_client, make_user):
    admin, _ = admin_client
    user = make_user(email="leaving@firm.mx")
    admin.post(f"/admin/users/{user.id}/disable")
    rows = {u["email"]: u["is_active"] for u in admin.get("/admin/users").json()}
    assert rows == {"admin@firm.mx": True, "leaving@firm.mx": False}


# --- changing your own password ------------------------------------------------------

def test_changing_the_password_signs_out_other_devices_but_not_this_one(logged_in_client, second_browser, client):
    here, user = logged_in_client
    login(second_browser, user.email)

    response = here.post(
        "/auth/change-password",
        json={"current_password": "password123", "new_password": "a brand new passphrase"},
    )

    assert response.status_code == 204
    assert here.get("/auth/me").status_code == 200
    assert second_browser.get("/auth/me").status_code == 401
    assert login(client, user.email, "password123").status_code == 401
    assert login(client, user.email, "a brand new passphrase").status_code == 200


def test_changing_the_password_needs_the_current_one(logged_in_client, db):
    client, user = logged_in_client
    response = client.post(
        "/auth/change-password",
        json={"current_password": "not mine", "new_password": "a brand new passphrase"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "wrong_password"
    assert login(client, user.email).status_code == 200, "the old password still works"
    assert any(e.detail == {"via": "change_password"} for e in entries(db, audit.LOGIN_FAILED))


def test_the_new_password_must_be_long_enough(logged_in_client):
    client, _ = logged_in_client
    response = client.post(
        "/auth/change-password", json={"current_password": "password123", "new_password": "short"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "password_too_short"
    assert response.json()["params"] == {"min": settings.MIN_PASSWORD_LENGTH}


def test_guessing_the_current_password_is_throttled_like_a_sign_in(logged_in_client, monkeypatch):
    client, _ = logged_in_client
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES_PER_ACCOUNT", 3)
    codes = [
        client.post(
            "/auth/change-password", json={"current_password": f"guess {i}", "new_password": "x" * 20}
        ).json().get("code")
        for i in range(5)
    ]
    assert codes[:3] == ["wrong_password"] * 3
    assert codes[3:] == ["too_many_attempts"] * 2


def test_changing_the_password_requires_a_session(client):
    response = client.post("/auth/change-password", json={"current_password": "a", "new_password": "b" * 20})
    assert response.status_code == 401


# --- administrator-issued password reset -------------------------------------------

def test_a_reset_link_sets_a_new_password_and_ends_old_sessions(admin_client, make_user, second_browser, third_browser, db):
    admin, _ = admin_client
    user = make_user(email="locked@firm.mx")
    login(second_browser, "locked@firm.mx")

    created = admin.post(f"/admin/users/{user.id}/password-reset")
    assert created.status_code == 201
    token = created.json()["invite_url"].rsplit("/", 1)[1]
    assert created.json()["kind"] == "reset"

    info = third_browser.get(f"/invites/{token}").json()
    assert info == {"email": "locked@firm.mx", "kind": "reset"}

    accepted = third_browser.post(f"/invites/{token}/accept", json={"password": "my own new passphrase"})
    assert accepted.status_code == 201
    assert third_browser.get("/auth/me").json()["email"] == "locked@firm.mx", "they are signed in straight away"
    assert second_browser.get("/auth/me").status_code == 401, "whoever had the old password is signed out"
    assert login(third_browser, "locked@firm.mx", "password123").status_code == 401
    assert login(third_browser, "locked@firm.mx", "my own new passphrase").status_code == 200

    # one use only
    assert third_browser.post(f"/invites/{token}/accept", json={"password": "another passphrase!!"}).status_code == 404
    assert entries(db, audit.PASSWORD_RESET_CREATED)[0].actor_email == "admin@firm.mx"
    assert entries(db, audit.PASSWORD_RESET_COMPLETED)[0].target == "locked@firm.mx"
    assert db.scalar(select(User).where(User.email == "locked@firm.mx")) is not None


def test_a_newer_reset_link_replaces_the_older_one(admin_client, make_user, second_browser):
    admin, _ = admin_client
    user = make_user(email="locked@firm.mx")
    first = admin.post(f"/admin/users/{user.id}/password-reset").json()["invite_url"].rsplit("/", 1)[1]
    second = admin.post(f"/admin/users/{user.id}/password-reset").json()["invite_url"].rsplit("/", 1)[1]
    assert second_browser.get(f"/invites/{first}").status_code == 404
    assert second_browser.get(f"/invites/{second}").status_code == 200


def test_a_reset_cannot_be_issued_for_a_disabled_account_or_used_after_disabling(admin_client, make_user, second_browser):
    admin, _ = admin_client
    user = make_user(email="locked@firm.mx")
    token = admin.post(f"/admin/users/{user.id}/password-reset").json()["invite_url"].rsplit("/", 1)[1]
    admin.post(f"/admin/users/{user.id}/disable")

    assert admin.post(f"/admin/users/{user.id}/password-reset").json()["code"] == "user_disabled"
    assert second_browser.post(f"/invites/{token}/accept", json={"password": "a long enough passphrase"}).status_code == 404


def test_a_reset_link_does_not_create_accounts_and_an_invite_cannot_reset(admin_client, client, make_user):
    admin, _ = admin_client
    make_user(email="exists@firm.mx")
    # an ordinary invite for an address that already has an account is refused
    assert admin.post("/admin/invites", json={"email": "exists@firm.mx"}).status_code == 409
    pending = admin.get("/admin/invites").json()
    assert pending == []


def test_pending_list_labels_resets(admin_client, make_user):
    admin, _ = admin_client
    user = make_user(email="locked@firm.mx")
    admin.post(f"/admin/users/{user.id}/password-reset")
    admin.post("/admin/invites", json={"email": "new@firm.mx"})
    kinds = {i["email"]: i["kind"] for i in admin.get("/admin/invites").json()}
    assert kinds == {"locked@firm.mx": "reset", "new@firm.mx": "invite"}


# --- pausing sign-in after repeated failures ----------------------------------------

def test_too_many_failures_for_one_account_pause_sign_in_even_with_the_right_password(client, make_user, db):
    make_user(email="target@firm.mx")
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_ACCOUNT):
        assert login(client, "target@firm.mx", "wrong").status_code == 401

    paused = login(client, "target@firm.mx", "password123")

    assert paused.status_code == 429
    assert paused.json()["code"] == "too_many_attempts"
    assert paused.json()["params"] == {"minutes": settings.LOGIN_WINDOW_MINUTES}
    assert paused.headers["retry-after"] == str(settings.LOGIN_WINDOW_MINUTES * 60)


def test_the_pause_is_recorded_once_not_on_every_attempt(client, make_user, db):
    make_user(email="target@firm.mx")
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_ACCOUNT):
        login(client, "target@firm.mx", "wrong")
    for _ in range(25):
        assert login(client, "target@firm.mx", "wrong").status_code == 429

    assert len(entries(db, audit.LOGIN_THROTTLED)) == 1
    assert len(entries(db, audit.LOGIN_FAILED)) == settings.LOGIN_MAX_FAILURES_PER_ACCOUNT, "no unbounded log growth"


def test_the_pause_ends_by_itself(client, make_user, db):
    make_user(email="target@firm.mx")
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_ACCOUNT):
        login(client, "target@firm.mx", "wrong")
    assert login(client, "target@firm.mx", "password123").status_code == 429

    old = utcnow() - timedelta(minutes=settings.LOGIN_WINDOW_MINUTES + 1)
    db.execute(update(AuditLog).where(AuditLog.action.in_([audit.LOGIN_FAILED, audit.LOGIN_THROTTLED])).values(occurred_at=old))
    db.commit()

    assert login(client, "target@firm.mx", "password123").status_code == 200


def test_one_account_being_paused_does_not_pause_others(client, make_user):
    make_user(email="target@firm.mx")
    make_user(email="other@firm.mx")
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_ACCOUNT):
        login(client, "target@firm.mx", "wrong")
    assert login(client, "other@firm.mx").status_code == 200


def test_too_many_failures_from_one_address_pause_every_account_from_it(client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES_PER_IP", 4)
    for i in range(4):
        make_user(email=f"user{i}@firm.mx")
        assert login(client, f"user{i}@firm.mx", "wrong").status_code == 401
    make_user(email="innocent@firm.mx")

    response = login(client, "innocent@firm.mx")

    assert response.status_code == 429


def test_a_successful_sign_in_is_not_counted_against_anyone(client, make_user):
    make_user()
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_ACCOUNT * 2):
        assert login(client, "alice@example.com").status_code == 200


def test_unknown_addresses_are_throttled_too(client):
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_ACCOUNT):
        assert login(client, "ghost@firm.mx", "x").status_code == 401
    assert login(client, "ghost@firm.mx", "x").status_code == 429


# --- invitation links -----------------------------------------------------------------

def test_invitation_lookups_are_rate_limited_per_address(client, monkeypatch):
    monkeypatch.setattr(invites_module, "_limiter", RateLimiter(3, 900))
    statuses = [client.get("/invites/not-a-real-token").status_code for _ in range(5)]
    assert statuses == [404, 404, 404, 429, 429]
    last = client.get("/invites/not-a-real-token")
    assert last.json()["code"] == "too_many_attempts"
    assert int(last.headers["retry-after"]) > 0


# --- the limiter itself -----------------------------------------------------------------

def test_rate_limiter_window_slides_and_keys_are_independent():
    now = [0.0]
    limiter = RateLimiter(2, 10, clock=lambda: now[0])
    assert limiter.allow("a") and limiter.allow("a")
    assert not limiter.allow("a")
    assert limiter.allow("b")
    assert limiter.retry_after("a") > 0
    now[0] = 11
    assert limiter.allow("a")
    assert limiter.retry_after("a") == 0


def test_a_disabled_account_is_refused_even_if_its_session_was_somehow_left_open(logged_in_client, db):
    """Defence in depth: the check does not rely on the sessions having been ended."""
    client, user = logged_in_client
    db.execute(update(User).where(User.id == user.id).values(is_active=False))
    db.commit()
    assert client.get("/auth/me").status_code == 401
