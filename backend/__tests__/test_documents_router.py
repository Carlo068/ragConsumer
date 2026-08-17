from sqlalchemy import select

from app.models import Collection, CollectionMember, Document, DocumentStatus


def _create_collection(db, user):
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.flush()
    db.add(CollectionMember(user_id=user.id, collection_id=collection.id))
    db.commit()
    return collection


def test_upload_rejects_file_over_the_size_limit(logged_in_client, db, monkeypatch):
    client, user = logged_in_client
    collection = _create_collection(db, user)
    monkeypatch.setattr("app.routers.documents.minio_client.put_object", lambda *a, **k: None)

    oversized = b"x" * (3 * 1024 * 1024)  # over the 2MB default limit
    response = client.post(
        f"/collections/{collection.id}/documents",
        files={"file": ("big.txt", oversized, "text/plain")},
    )

    assert response.status_code == 413


def test_upload_accepts_file_under_the_limit(logged_in_client, db, monkeypatch):
    client, user = logged_in_client
    collection = _create_collection(db, user)
    put_calls = []
    monkeypatch.setattr(
        "app.routers.documents.minio_client.put_object",
        lambda *a, **k: put_calls.append((a, k)),
    )

    response = client.post(
        f"/collections/{collection.id}/documents",
        files={"file": ("small.txt", b"hello world", "text/plain")},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "uploaded"
    assert len(put_calls) == 1


def test_upload_requires_membership(client, make_user, db, monkeypatch):
    owner = make_user(email="alice@example.com")
    make_user(email="bob@example.com")
    collection = _create_collection(db, owner)
    monkeypatch.setattr("app.routers.documents.minio_client.put_object", lambda *a, **k: None)

    client.post("/auth/login", json={"email": "bob@example.com", "password": "password123"})
    response = client.post(
        f"/collections/{collection.id}/documents",
        files={"file": ("small.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 404


def test_delete_document_cleans_up_minio_and_qdrant(logged_in_client, db, monkeypatch):
    client, user = logged_in_client
    collection = _create_collection(db, user)
    document = Document(
        collection_id=collection.id,
        uploaded_by=user.id,
        source_filename="report.txt",
        object_key=f"collection-{collection.id}/doc-x/report.txt",
        status=DocumentStatus.ready,
    )
    db.add(document)
    db.commit()
    # Captured before the delete request: once that runs (in a different
    # session), this row is gone, and accessing an expired attribute on an
    # instance this session cached would try to refresh from a row that no
    # longer exists, raising ObjectDeletedError instead of reading the
    # last-known value.
    document_uuid = document.id
    collection_id = str(collection.id)
    document_id = str(document_uuid)
    object_key = document.object_key

    deleted_doc_ids: list[str] = []
    deleted_keys: list[str] = []
    monkeypatch.setattr("app.routers.documents.delete_document_chunks", deleted_doc_ids.append)
    monkeypatch.setattr("app.routers.documents.delete_object", deleted_keys.append)

    response = client.delete(f"/collections/{collection_id}/documents/{document_id}")

    assert response.status_code == 204
    assert deleted_doc_ids == [document_id]
    assert deleted_keys == [object_key]
    # A plain select() (rather than db.get(), which special-cases a row it
    # already had loaded and would raise ObjectDeletedError instead of just
    # reporting "not found") confirms the row is really gone.
    remaining = db.execute(select(Document).where(Document.id == document_uuid)).scalar_one_or_none()
    assert remaining is None


def test_delete_document_404s_for_a_document_in_a_different_collection(
    logged_in_client, db, monkeypatch
):
    client, user = logged_in_client
    collection = _create_collection(db, user)
    other_collection = Collection(name="Smith v. Jones")
    db.add(other_collection)
    db.flush()
    db.add(CollectionMember(user_id=user.id, collection_id=other_collection.id))
    document = Document(
        collection_id=other_collection.id,
        uploaded_by=user.id,
        source_filename="report.txt",
        object_key=f"collection-{other_collection.id}/doc-x/report.txt",
        status=DocumentStatus.ready,
    )
    db.add(document)
    db.commit()

    called = []
    monkeypatch.setattr("app.routers.documents.delete_object", called.append)

    # document exists, but under a different (also-member) collection_id in
    # the URL -- must not be deletable via the wrong collection's path
    response = client.delete(f"/collections/{collection.id}/documents/{document.id}")

    assert response.status_code == 404
    assert called == []
