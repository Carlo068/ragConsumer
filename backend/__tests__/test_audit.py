import csv
import io

import pytest
from datetime import datetime, timedelta

from sqlalchemy import select, text

from app import audit
from app.models import AuditLog, Collection, CollectionMember, CollectionRole


def entries(db, action=None):
    db.expire_all()
    # SQLite's timestamps only have one-second resolution (Postgres has
    # microseconds), so insertion order is the reliable order here.
    query = select(AuditLog).order_by(text("rowid"))
    rows = db.scalars(query).all()
    return [r for r in rows if action is None or r.action == action]


def login(client, email, password="password123"):
    client.post("/auth/logout")
    return client.post("/auth/login", json={"email": email, "password": password})


@pytest.fixture
def matter(db):
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.commit()
    return collection


@pytest.fixture
def owner_client(client, make_user, db, matter):
    user = make_user("owner@firm.mx")
    db.add(CollectionMember(user_id=user.id, collection_id=matter.id, role=CollectionRole.owner))
    db.commit()
    login(client, "owner@firm.mx")
    return client, user


# ---- what gets recorded ----

def test_successful_login_is_recorded(client, make_user, db):
    user = make_user("ana@firm.mx")
    login(client, "ana@firm.mx")
    [entry] = entries(db, audit.LOGIN)
    assert entry.actor_email == "ana@firm.mx" and entry.actor_user_id == user.id


def test_failed_login_is_recorded_without_the_password(client, make_user, db):
    make_user("ana@firm.mx")
    assert login(client, "ana@firm.mx", "wrong-password-123").status_code == 401
    assert login(client, "nobody@firm.mx", "wrong-password-123").status_code == 401
    failed = entries(db, audit.LOGIN_FAILED)
    assert [e.target for e in failed] == ["ana@firm.mx", "nobody@firm.mx"]
    assert all("wrong-password" not in str(vars(e)) for e in failed)


def test_invite_lifecycle_is_recorded(admin_client, db):
    client, admin = admin_client
    created = client.post("/admin/invites", json={"email": "New@Firm.mx"}).json()
    token = created["invite_url"].rsplit("/", 1)[1]
    client.delete(f"/admin/invites/{created['id']}")
    created = client.post("/admin/invites", json={"email": "new@firm.mx"}).json()
    token = created["invite_url"].rsplit("/", 1)[1]
    client.post(f"/invites/{token}/accept", json={"password": "a-long-passphrase"})

    assert [(e.action, e.target) for e in entries(db) if e.action.startswith("invite")] == [
        (audit.INVITE_CREATED, "new@firm.mx"),
        (audit.INVITE_REVOKED, "new@firm.mx"),
        (audit.INVITE_CREATED, "new@firm.mx"),
        (audit.INVITE_ACCEPTED, "new@firm.mx"),
    ]
    assert entries(db, audit.INVITE_CREATED)[0].actor_email == admin.email


def test_matter_lifecycle_is_recorded_with_names_that_survive_deletion(
    client, logged_in_client, db, monkeypatch
):
    monkeypatch.setattr("app.routers.collections.delete_matter_vectors", lambda _: None)
    monkeypatch.setattr("app.routers.collections.delete_objects_by_prefix", lambda _: None)
    client, _ = logged_in_client
    matter_id = client.post("/collections", json={"name": "Old name"}).json()["id"]
    client.patch(f"/collections/{matter_id}", json={"name": "New name"})
    client.delete(f"/collections/{matter_id}")

    created, renamed, deleted = (
        entries(db, audit.MATTER_CREATED)[0],
        entries(db, audit.MATTER_RENAMED)[0],
        entries(db, audit.MATTER_DELETED)[0],
    )
    assert created.collection_name == "Old name"
    assert renamed.collection_name == "New name" and renamed.detail == {"previous_name": "Old name"}
    # The matter row is gone, but its log entries still say which matter it was.
    assert deleted.collection_name == "New name" and str(deleted.collection_id) == matter_id


def test_documents_members_tokens_and_ai_access_are_recorded(
    owner_client, make_user, db, matter, monkeypatch
):
    client, _ = owner_client
    monkeypatch.setattr("app.routers.documents.minio_client.put_object", lambda *a, **k: None)
    monkeypatch.setattr("app.routers.documents.delete_object", lambda *_: None)
    monkeypatch.setattr("app.routers.documents.delete_document_chunks", lambda *_: None)
    make_user("beto@firm.mx")
    beto_id = client.post(
        f"/collections/{matter.id}/members", json={"email": "beto@firm.mx", "role": "viewer"}
    ).json()["user_id"]
    client.patch(f"/collections/{matter.id}/members/{beto_id}", json={"role": "editor"})
    client.delete(f"/collections/{matter.id}/members/{beto_id}")
    doc = client.post(
        f"/collections/{matter.id}/documents", files={"file": ("contrato.pdf", b"x", "application/pdf")}
    ).json()
    client.delete(f"/collections/{matter.id}/documents/{doc['id']}")
    token = client.post("/tokens", json={"name": "Laptop"}).json()
    client.delete(f"/tokens/{token['id']}")
    client.put(f"/collections/{matter.id}/ai-access")
    client.delete(f"/collections/{matter.id}/ai-access")

    got = [(e.action, e.target) for e in entries(db) if e.action != audit.LOGIN]
    assert got == [
        (audit.MEMBER_ADDED, "beto@firm.mx"),
        (audit.MEMBER_ROLE_CHANGED, "beto@firm.mx"),
        (audit.MEMBER_REMOVED, "beto@firm.mx"),
        (audit.DOCUMENT_UPLOADED, "contrato.pdf"),
        (audit.DOCUMENT_DELETED, "contrato.pdf"),
        (audit.TOKEN_CREATED, "Laptop"),
        (audit.TOKEN_REVOKED, "Laptop"),
        (audit.AI_ACCESS_ENABLED, None),
        (audit.AI_ACCESS_DISABLED, None),
    ]
    assert entries(db, audit.MEMBER_ROLE_CHANGED)[0].detail == {"role": "editor", "previous_role": "viewer"}
    # Matter-scoped entries carry the matter; token entries never contain the secret.
    assert entries(db, audit.DOCUMENT_UPLOADED)[0].collection_name == "Doe Estate"
    assert token["token"] not in str([vars(e) for e in entries(db)])


def test_a_refused_action_is_recorded_only_as_a_refusal(client, make_user, db, matter):
    make_user("outsider@firm.mx")
    login(client, "outsider@firm.mx")
    before = len(entries(db))
    assert client.put(f"/collections/{matter.id}/ai-access").status_code == 404
    assert client.delete(f"/collections/{matter.id}").status_code == 404
    # Nothing is recorded as if the action had happened; the refusals themselves are
    # recorded as such (see test_denied_access.py).
    new = entries(db)[before:]
    assert [e.action for e in new] == [audit.ACCESS_DENIED, audit.ACCESS_DENIED]


# ---- who can read it ----

def test_only_admins_can_read_the_log(client, make_user, logged_in_client):
    c, _ = logged_in_client
    assert c.get("/admin/audit").status_code == 403
    assert c.get("/admin/audit.csv").status_code == 403


def test_requires_login(client):
    assert client.get("/admin/audit").status_code == 401


def test_admin_sees_newest_first_with_paging_and_filters(admin_client, db, matter):
    client, admin = admin_client
    base = datetime(2026, 11, 13, 9, 0, 0)
    for i, name in enumerate(("A", "B", "C")):
        db.add(
            AuditLog(
                occurred_at=base + timedelta(minutes=i), actor_user_id=admin.id,
                actor_email=admin.email, action=audit.MATTER_CREATED,
                collection_id=matter.id, collection_name=matter.name, target=name,
            )
        )
    audit.record(db, audit.LOGIN_FAILED, target="x@firm.mx")
    db.commit()

    page = client.get("/admin/audit", params={"limit": 2}).json()
    assert page["total"] >= 5 and len(page["items"]) == 2

    only = client.get("/admin/audit", params={"action": audit.MATTER_CREATED}).json()
    assert [i["target"] for i in only["items"]] == ["C", "B", "A"]
    by_matter = client.get("/admin/audit", params={"collection_id": str(matter.id)}).json()
    assert by_matter["total"] == 3
    by_actor = client.get("/admin/audit", params={"actor": "ADMIN@"}).json()
    assert by_actor["total"] >= 3


# ---- append-only from the application's side ----

def test_the_app_exposes_no_way_to_change_or_delete_entries(client):
    paths = client.app.openapi()["paths"]
    routes = {
        (method.upper(), path)
        for path, operations in paths.items()
        for method in operations
        if "audit" in path
    }
    assert routes == {("GET", "/admin/audit"), ("GET", "/admin/audit.csv")}


# ---- CSV export ----

def test_csv_export_has_a_header_and_the_entries(admin_client, db):
    client, admin = admin_client
    audit.record(db, audit.TOKEN_CREATED, actor=admin, target="Portátil de Ana")
    db.commit()
    response = client.get("/admin/audit.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0] == ["occurred_at_utc", "actor", "action", "matter", "target", "detail", "ip"]
    assert any(r[2] == audit.TOKEN_CREATED and r[4] == "Portátil de Ana" for r in rows[1:])


@pytest.mark.parametrize("payload", ["=HYPERLINK(\"http://evil\")", "+1+1", "-2+3", "@SUM(A1)"])
def test_csv_export_defuses_spreadsheet_formulas(admin_client, db, payload):
    client, admin = admin_client
    audit.record(db, audit.DOCUMENT_UPLOADED, actor=admin, target=payload)
    db.commit()
    rows = list(csv.reader(io.StringIO(client.get("/admin/audit.csv").content.decode("utf-8-sig"))))
    cell = next(r[4] for r in rows[1:] if r[2] == audit.DOCUMENT_UPLOADED)
    assert cell == "'" + payload
