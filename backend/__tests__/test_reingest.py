import pytest
from sqlalchemy import select

from app import audit
from app.models import AuditLog, Collection, CollectionMember, CollectionRole, Document, DocumentStatus

ALL_ROLES = [None, CollectionRole.viewer, CollectionRole.editor, CollectionRole.owner]


@pytest.fixture
def matter_with_failed_doc(db, make_user):
    owner = make_user("owner@firm.mx")
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.flush()
    db.add(CollectionMember(user_id=owner.id, collection_id=collection.id, role=CollectionRole.owner))
    document = Document(
        collection_id=collection.id,
        uploaded_by=owner.id,
        source_filename="escaneo.pdf",
        object_key="collection-x/doc-y/escaneo.pdf",
        status=DocumentStatus.failed,
        error_message="No text could be found in this file.",
    )
    db.add(document)
    db.commit()
    return collection, document


@pytest.fixture
def deleted_chunks(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.routers.documents.delete_document_chunks", lambda m, d: calls.append((m, d))
    )
    return calls


def login(client, email):
    client.post("/auth/logout")
    assert client.post("/auth/login", json={"email": email, "password": "password123"}).status_code == 200


def set_status(db, document, status):
    db.expire_all()
    doc = db.get(Document, document.id)
    doc.status = status
    db.commit()


def test_the_failure_reason_is_shown_in_the_file_list(client, matter_with_failed_doc):
    collection, _ = matter_with_failed_doc
    login(client, "owner@firm.mx")
    [row] = client.get(f"/collections/{collection.id}/documents").json()
    assert row["status"] == "failed"
    assert row["error_message"] == "No text could be found in this file."


def test_retry_puts_the_file_back_in_the_queue_and_clears_the_reason(
    client, db, matter_with_failed_doc, deleted_chunks
):
    collection, document = matter_with_failed_doc
    login(client, "owner@firm.mx")
    response = client.post(f"/collections/{collection.id}/documents/{document.id}/reingest")

    assert response.status_code == 200
    assert response.json()["status"] == "uploaded" and response.json()["error_message"] is None
    db.expire_all()
    assert db.get(Document, document.id).status == DocumentStatus.uploaded
    # Whatever was indexed before is removed so a retry can't leave stale passages.
    assert deleted_chunks == [(str(collection.id), str(document.id))]


@pytest.mark.parametrize("status", [DocumentStatus.ready, DocumentStatus.uploaded])
def test_a_ready_or_waiting_file_can_also_be_reindexed(
    client, db, matter_with_failed_doc, deleted_chunks, status
):
    collection, document = matter_with_failed_doc
    set_status(db, document, status)
    login(client, "owner@firm.mx")
    assert client.post(f"/collections/{collection.id}/documents/{document.id}/reingest").status_code == 200


def test_a_file_being_processed_right_now_cannot_be_retried(
    client, db, matter_with_failed_doc, deleted_chunks
):
    collection, document = matter_with_failed_doc
    set_status(db, document, DocumentStatus.processing)
    login(client, "owner@firm.mx")
    response = client.post(f"/collections/{collection.id}/documents/{document.id}/reingest")
    assert response.status_code == 409
    assert deleted_chunks == []


@pytest.mark.parametrize("role", ALL_ROLES, ids=lambda r: r.value if r else "non-member")
def test_retry_needs_the_editor_role(role, client, db, make_user, matter_with_failed_doc, deleted_chunks):
    collection, document = matter_with_failed_doc
    other = make_user("other@firm.mx")
    if role:
        db.add(CollectionMember(user_id=other.id, collection_id=collection.id, role=role))
        db.commit()
    login(client, "other@firm.mx")

    response = client.post(f"/collections/{collection.id}/documents/{document.id}/reingest")

    expected = {None: 404, CollectionRole.viewer: 403}.get(role, 200)
    assert response.status_code == expected
    if expected != 200:
        db.expire_all()
        assert db.get(Document, document.id).status == DocumentStatus.failed
        assert deleted_chunks == []


def test_a_document_of_another_matter_cannot_be_retried_through_this_one(
    client, db, make_user, matter_with_failed_doc, deleted_chunks
):
    _, document = matter_with_failed_doc
    mine = Collection(name="Mine")
    me = make_user("me@firm.mx")
    db.add(mine)
    db.flush()
    db.add(CollectionMember(user_id=me.id, collection_id=mine.id, role=CollectionRole.owner))
    db.commit()
    login(client, "me@firm.mx")
    assert client.post(f"/collections/{mine.id}/documents/{document.id}/reingest").status_code == 404


def test_retry_is_recorded_in_the_audit_log(client, db, matter_with_failed_doc, deleted_chunks):
    collection, document = matter_with_failed_doc
    login(client, "owner@firm.mx")
    client.post(f"/collections/{collection.id}/documents/{document.id}/reingest")
    db.expire_all()
    entry = db.scalars(select(AuditLog).where(AuditLog.action == audit.DOCUMENT_REINGESTED)).one()
    assert entry.target == "escaneo.pdf" and entry.collection_name == "Doe Estate"
