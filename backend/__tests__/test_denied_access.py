"""Refused matter requests are recorded (KAN-98)."""

import uuid

import pytest
from sqlalchemy import select

from app import audit, denied
from app.models import AuditLog, Collection, CollectionMember, CollectionRole


def entries(db):
    db.expire_all()
    return list(db.scalars(select(AuditLog).where(AuditLog.action == audit.ACCESS_DENIED)))


@pytest.fixture
def matter(db):
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.commit()
    return collection


def test_asking_for_a_matter_you_do_not_belong_to_is_refused_and_recorded(logged_in_client, matter, db):
    client, user = logged_in_client

    response = client.get(f"/collections/{matter.id}/documents")

    assert response.status_code == 404
    [entry] = entries(db)
    assert entry.actor_email == user.email
    assert entry.collection_id == matter.id
    assert entry.collection_name == "Doe Estate"
    assert entry.detail == {"code": "matter_not_found", "status": 404}
    assert entry.target == f"GET /collections/{matter.id}/documents"


def test_a_role_too_low_for_the_action_is_recorded(logged_in_client, matter, db):
    client, user = logged_in_client
    db.add(CollectionMember(user_id=user.id, collection_id=matter.id, role=CollectionRole.viewer))
    db.commit()

    response = client.post(f"/collections/{matter.id}/documents", files={"file": ("a.txt", b"hola", "text/plain")})

    assert response.status_code == 403
    [entry] = entries(db)
    assert entry.detail == {"code": "role_required", "status": 403}


def test_a_matter_that_does_not_exist_is_recorded_the_same_way(logged_in_client, db):
    client, _ = logged_in_client
    ghost = uuid.uuid4()

    assert client.get(f"/collections/{ghost}/documents").status_code == 404

    [entry] = entries(db)
    assert entry.collection_id == ghost and entry.collection_name is None


def test_normal_use_leaves_no_entry(logged_in_client, matter, db):
    client, user = logged_in_client
    db.add(CollectionMember(user_id=user.id, collection_id=matter.id, role=CollectionRole.owner))
    db.commit()

    assert client.get(f"/collections/{matter.id}/documents").status_code == 200
    assert entries(db) == []


def test_someone_who_is_not_signed_in_is_not_recorded(client, matter, db):
    assert client.get(f"/collections/{matter.id}/documents").status_code == 401
    assert entries(db) == []


def test_a_failure_to_record_never_changes_the_answer(logged_in_client, matter, db, monkeypatch):
    client, _ = logged_in_client

    def boom(*args, **kwargs):
        raise RuntimeError("database is having a bad day")

    monkeypatch.setattr(audit, "record", boom)

    response = client.get(f"/collections/{matter.id}/documents")

    assert response.status_code == 404
    assert response.json()["code"] == "matter_not_found"


def test_the_codes_recorded_are_only_about_matters():
    assert denied.DENIED_CODES == {"matter_not_found", "role_required"}
