from sqlalchemy import select

from app.models import Collection, CollectionMember, Document, DocumentStatus


def test_create_collection_adds_creator_as_member(logged_in_client):
    client, _ = logged_in_client

    response = client.post("/collections", json={"name": "Doe Estate"})
    assert response.status_code == 201
    collection_id = response.json()["id"]

    # only visible via GET /collections if the creator was actually added
    # as a collection_members row, not just the collections row itself
    list_response = client.get("/collections")
    assert any(c["id"] == collection_id for c in list_response.json())


def test_rename_requires_membership(client, make_user, db):
    owner = make_user(email="alice@example.com")
    make_user(email="bob@example.com")
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.flush()
    db.add(CollectionMember(user_id=owner.id, collection_id=collection.id))
    db.commit()

    client.post("/auth/login", json={"email": "bob@example.com", "password": "password123"})
    response = client.patch(f"/collections/{collection.id}", json={"name": "Hacked"})

    assert response.status_code == 404


def test_rename_updates_name_for_a_member(logged_in_client, db):
    client, user = logged_in_client
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.flush()
    db.add(CollectionMember(user_id=user.id, collection_id=collection.id))
    db.commit()

    response = client.patch(f"/collections/{collection.id}", json={"name": "Renamed"})

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"


def test_delete_collection_cleans_up_minio_and_qdrant(logged_in_client, db, monkeypatch):
    client, user = logged_in_client
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.flush()
    db.add(CollectionMember(user_id=user.id, collection_id=collection.id))
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
    # session), these rows are gone, and accessing an expired attribute on
    # an instance this session cached would try to refresh from a row that
    # no longer exists, raising ObjectDeletedError instead of just reading
    # the last-known value.
    collection_uuid = collection.id
    collection_id = str(collection_uuid)
    document_id = str(document.id)

    deleted_doc_ids: list[str] = []
    deleted_prefixes: list[str] = []
    monkeypatch.setattr(
        "app.routers.collections.delete_document_chunks", deleted_doc_ids.append
    )
    monkeypatch.setattr(
        "app.routers.collections.delete_objects_by_prefix", deleted_prefixes.append
    )

    response = client.delete(f"/collections/{collection_id}")

    assert response.status_code == 204
    # cleanup must happen for every document in the collection, keyed by doc
    # id (Qdrant) and by the collection's MinIO prefix, not per-document keys
    assert deleted_doc_ids == [document_id]
    assert deleted_prefixes == [f"collection-{collection_id}/"]
    # A plain select() (rather than db.get(), which special-cases a row it
    # already had loaded and would raise ObjectDeletedError instead of just
    # reporting "not found") confirms the DB cascade actually ran.
    remaining = db.execute(select(Collection).where(Collection.id == collection_uuid)).scalar_one_or_none()
    assert remaining is None


def test_delete_collection_requires_membership(client, make_user, db, monkeypatch):
    owner = make_user(email="alice@example.com")
    make_user(email="bob@example.com")
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.flush()
    db.add(CollectionMember(user_id=owner.id, collection_id=collection.id))
    db.commit()

    called = []
    monkeypatch.setattr("app.routers.collections.delete_objects_by_prefix", called.append)

    client.post("/auth/login", json={"email": "bob@example.com", "password": "password123"})
    response = client.delete(f"/collections/{collection.id}")

    assert response.status_code == 404
    assert called == []  # never even attempted cleanup for a collection bob can't touch
    assert db.get(Collection, collection.id) is not None
