"""Per-matter roles, enforced by the server.

Each route is tried as every role (and as a non-member), because the failure
mode that matters for a law firm is a role being allowed to do more than it
should.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Collection, CollectionMember, CollectionRole, Document, DocumentStatus

OWNER, EDITOR, VIEWER = CollectionRole.owner, CollectionRole.editor, CollectionRole.viewer


@pytest.fixture
def matter(db, make_user):
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.commit()
    return collection


def _login_as(role, db, make_user, matter, monkeypatch):
    """A fresh client logged in as a user holding `role` on the matter
    (role=None means a registered user who is NOT a member)."""
    user = make_user(email=f"{role.value if role else 'outsider'}@firm.mx")
    if role is not None:
        db.add(CollectionMember(user_id=user.id, collection_id=matter.id, role=role))
        db.commit()
    client = TestClient(app)
    client.__enter__()
    assert client.post(
        "/auth/login", json={"email": user.email, "password": "password123"}
    ).status_code == 200
    # Never touch real MinIO/Qdrant, whatever a route decides to call.
    monkeypatch.setattr("app.routers.documents.minio_client.put_object", lambda *a, **k: None)
    monkeypatch.setattr("app.routers.documents.delete_object", lambda *a, **k: None)
    monkeypatch.setattr("app.routers.documents.delete_document_chunks", lambda *a, **k: None)
    monkeypatch.setattr("app.routers.collections.delete_objects_by_prefix", lambda *a, **k: None)
    monkeypatch.setattr("app.routers.collections.delete_document_chunks", lambda *a, **k: None)
    return client


def _document(db, matter, user_id):
    doc = Document(
        collection_id=matter.id,
        uploaded_by=user_id,
        source_filename="x.txt",
        object_key=f"collection-{matter.id}/doc-x/x.txt",
        status=DocumentStatus.ready,
    )
    db.add(doc)
    db.commit()
    return str(doc.id)


# Expected HTTP status per role for each action. 404 = "no such matter"
# (non-member), 403 = "you're a member but your role is too low".
RENAME = {OWNER: 200, EDITOR: 403, VIEWER: 403, None: 404}
DELETE_MATTER = {OWNER: 204, EDITOR: 403, VIEWER: 403, None: 404}
UPLOAD = {OWNER: 201, EDITOR: 201, VIEWER: 403, None: 404}
LIST_FILES = {OWNER: 200, EDITOR: 200, VIEWER: 200, None: 404}
DELETE_FILE = {OWNER: 204, EDITOR: 204, VIEWER: 403, None: 404}
ALL_ROLES = [OWNER, EDITOR, VIEWER, None]


@pytest.mark.parametrize("role", ALL_ROLES, ids=lambda r: r.value if r else "non-member")
def test_rename_needs_owner(role, db, make_user, matter, monkeypatch):
    client = _login_as(role, db, make_user, matter, monkeypatch)
    response = client.patch(f"/collections/{matter.id}", json={"name": "Renamed"})
    assert response.status_code == RENAME[role]


@pytest.mark.parametrize("role", ALL_ROLES, ids=lambda r: r.value if r else "non-member")
def test_delete_matter_needs_owner(role, db, make_user, matter, monkeypatch):
    client = _login_as(role, db, make_user, matter, monkeypatch)
    assert client.delete(f"/collections/{matter.id}").status_code == DELETE_MATTER[role]


@pytest.mark.parametrize("role", ALL_ROLES, ids=lambda r: r.value if r else "non-member")
def test_upload_needs_editor(role, db, make_user, matter, monkeypatch):
    client = _login_as(role, db, make_user, matter, monkeypatch)
    response = client.post(
        f"/collections/{matter.id}/documents", files={"file": ("a.txt", b"hola", "text/plain")}
    )
    assert response.status_code == UPLOAD[role]


@pytest.mark.parametrize("role", ALL_ROLES, ids=lambda r: r.value if r else "non-member")
def test_list_files_needs_any_role(role, db, make_user, matter, monkeypatch):
    client = _login_as(role, db, make_user, matter, monkeypatch)
    assert client.get(f"/collections/{matter.id}/documents").status_code == LIST_FILES[role]


@pytest.mark.parametrize("role", ALL_ROLES, ids=lambda r: r.value if r else "non-member")
def test_delete_file_needs_editor(role, db, make_user, matter, monkeypatch):
    client = _login_as(role, db, make_user, matter, monkeypatch)
    doc_id = _document(db, matter, db.query(CollectionMember).first().user_id if role else make_user("x@firm.mx").id)
    response = client.delete(f"/collections/{matter.id}/documents/{doc_id}")
    assert response.status_code == DELETE_FILE[role]


def test_denied_actions_change_nothing(db, make_user, matter, monkeypatch):
    """A 403 must not have done the thing anyway."""
    client = _login_as(VIEWER, db, make_user, matter, monkeypatch)
    client.patch(f"/collections/{matter.id}", json={"name": "Hacked"})
    client.delete(f"/collections/{matter.id}")
    db.expire_all()
    assert db.get(Collection, matter.id).name == "Doe Estate"


# --- The role is reported correctly, and scoped per matter ---------------


def test_list_reports_the_callers_role_per_matter(db, make_user):
    user = make_user(email="mixed@firm.mx")
    owned, viewed = Collection(name="Owned"), Collection(name="Viewed")
    db.add_all([owned, viewed])
    db.flush()
    db.add(CollectionMember(user_id=user.id, collection_id=owned.id, role=OWNER))
    db.add(CollectionMember(user_id=user.id, collection_id=viewed.id, role=VIEWER))
    db.commit()
    with TestClient(app) as client:
        client.post("/auth/login", json={"email": user.email, "password": "password123"})
        roles = {c["name"]: c["role"] for c in client.get("/collections").json()}
    assert roles == {"Owned": "owner", "Viewed": "viewer"}


def test_role_on_one_matter_grants_nothing_on_another(db, make_user, matter, monkeypatch):
    other = Collection(name="Other matter")
    db.add(other)
    db.commit()
    client = _login_as(OWNER, db, make_user, matter, monkeypatch)  # owner of `matter` only
    assert client.patch(f"/collections/{other.id}", json={"name": "x"}).status_code == 404
    assert client.get(f"/collections/{other.id}/documents").status_code == 404


def test_creating_a_matter_makes_you_its_owner(logged_in_client):
    client, _ = logged_in_client
    created = client.post("/collections", json={"name": "New matter"})
    assert created.status_code == 201 and created.json()["role"] == "owner"
    assert client.patch(f"/collections/{created.json()['id']}", json={"name": "Renamed"}).status_code == 200


def test_a_membership_without_a_role_cannot_exist(db, make_user, matter):
    """The column has no default on purpose: forgetting the role must fail
    loudly, not silently grant some permission level."""
    from sqlalchemy.exc import IntegrityError

    user = make_user(email="norole@firm.mx")
    db.add(CollectionMember(user_id=user.id, collection_id=matter.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
