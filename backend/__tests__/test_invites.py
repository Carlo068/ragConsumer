from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import Collection, CollectionMember, CollectionRole, Invite
from app.routers.admin import utcnow

STRONG_PASSWORD = "a-long-passphrase"


def _token_from(invite_url: str) -> str:
    return invite_url.rsplit("/", 1)[-1]


def _invite(client, email="nuevo@firm.mx") -> str:
    response = client.post("/admin/invites", json={"email": email})
    assert response.status_code == 201
    return _token_from(response.json()["invite_url"])


# --- Who can invite --------------------------------------------------------


def test_unauthenticated_user_cannot_invite(client):
    response = client.post("/admin/invites", json={"email": "x@firm.mx"})
    assert response.status_code == 401


def test_non_admin_cannot_invite_or_list_users(logged_in_client):
    client, _ = logged_in_client
    assert client.post("/admin/invites", json={"email": "x@firm.mx"}).status_code == 403
    assert client.get("/admin/users").status_code == 403
    assert client.get("/admin/invites").status_code == 403


def test_admin_cannot_invite_an_existing_user(admin_client, make_user):
    client, _ = admin_client
    make_user(email="taken@firm.mx")
    response = client.post("/admin/invites", json={"email": "Taken@Firm.mx"})
    assert response.status_code == 409


def test_raw_token_is_never_stored(admin_client, db):
    client, _ = admin_client
    token = _invite(client)
    stored = db.scalar(select(Invite))
    assert stored.token_hash != token
    assert token not in stored.token_hash


# --- Accepting -----------------------------------------------------------


def test_invite_lookup_shows_the_invited_email(admin_client):
    client, _ = admin_client
    token = _invite(client, email="Nuevo@Firm.mx")
    with TestClient(app) as invitee:
        response = invitee.get(f"/invites/{token}")
    assert response.status_code == 200
    assert response.json() == {"email": "nuevo@firm.mx", "kind": "invite"}


def test_accepting_creates_a_non_admin_user_and_logs_them_in(admin_client):
    client, _ = admin_client
    token = _invite(client)
    with TestClient(app) as invitee:
        response = invitee.post(f"/invites/{token}/accept", json={"password": STRONG_PASSWORD})
        assert response.status_code == 201
        assert response.json()["email"] == "nuevo@firm.mx"
        assert response.json()["is_admin"] is False
        me = invitee.get("/auth/me")
        assert me.status_code == 200 and me.json()["email"] == "nuevo@firm.mx"

    # and the new account works for a normal login afterwards
    with TestClient(app) as fresh:
        login = fresh.post(
            "/auth/login", json={"email": "nuevo@firm.mx", "password": STRONG_PASSWORD}
        )
        assert login.status_code == 200


def test_short_password_is_rejected_and_invite_stays_usable(admin_client):
    client, _ = admin_client
    token = _invite(client)
    with TestClient(app) as invitee:
        assert invitee.post(f"/invites/{token}/accept", json={"password": "short"}).status_code == 422
        assert invitee.get(f"/invites/{token}").status_code == 200


def test_invite_link_is_single_use(admin_client):
    client, _ = admin_client
    token = _invite(client)
    with TestClient(app) as invitee:
        assert invitee.post(f"/invites/{token}/accept", json={"password": STRONG_PASSWORD}).status_code == 201
        again = invitee.post(f"/invites/{token}/accept", json={"password": STRONG_PASSWORD})
        assert again.status_code == 404


def test_expired_invite_is_rejected(admin_client, db):
    client, _ = admin_client
    token = _invite(client)
    invite = db.scalar(select(Invite))
    invite.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    with TestClient(app) as invitee:
        assert invitee.get(f"/invites/{token}").status_code == 404
        assert invitee.post(f"/invites/{token}/accept", json={"password": STRONG_PASSWORD}).status_code == 404


def test_unknown_token_is_rejected(client):
    assert client.get("/invites/not-a-real-token").status_code == 404


def test_reinviting_invalidates_the_previous_link(admin_client):
    client, _ = admin_client
    old_token = _invite(client)
    new_token = _invite(client)
    with TestClient(app) as invitee:
        assert invitee.get(f"/invites/{old_token}").status_code == 404
        assert invitee.get(f"/invites/{new_token}").status_code == 200


def test_revoked_invite_stops_working(admin_client):
    client, _ = admin_client
    token = _invite(client)
    invite_id = client.get("/admin/invites").json()[0]["id"]
    assert client.delete(f"/admin/invites/{invite_id}").status_code == 204
    with TestClient(app) as invitee:
        assert invitee.get(f"/invites/{token}").status_code == 404


def test_pending_list_excludes_accepted_invites(admin_client):
    client, _ = admin_client
    token = _invite(client)
    with TestClient(app) as invitee:
        invitee.post(f"/invites/{token}/accept", json={"password": STRONG_PASSWORD})
    assert client.get("/admin/invites").json() == []


# --- Admin is not a back door into matters ---------------------------------


def test_admin_gets_no_automatic_access_to_matters(admin_client, make_user, db):
    """Ethical walls: being the firm admin must not reveal anyone's matters."""
    client, _ = admin_client
    lawyer = make_user(email="abogado@firm.mx")
    matter = Collection(name="Confidential matter")
    db.add(matter)
    db.flush()
    db.add(CollectionMember(user_id=lawyer.id, collection_id=matter.id, role=CollectionRole.owner))
    db.commit()

    assert client.get("/collections").json() == []
    assert client.get(f"/collections/{matter.id}/documents").status_code == 404
