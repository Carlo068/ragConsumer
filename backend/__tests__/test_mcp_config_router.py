from app.models import Collection, CollectionMember


def test_active_collection_defaults_to_null(logged_in_client):
    client, _ = logged_in_client

    response = client.get("/mcp/active-collection")

    assert response.status_code == 200
    assert response.json() == {"collection_id": None, "collection_name": None}


def test_set_active_collection_requires_membership(logged_in_client, db):
    """The require_collection_membership gate on PUT /mcp/active-collection
    -- a user can't put the shared MCP server on a collection they don't
    belong to, even though nothing about querying the MCP server itself
    checks membership."""
    client, _ = logged_in_client
    other_collection = Collection(name="Someone Else's")
    db.add(other_collection)
    db.commit()

    response = client.put(
        "/mcp/active-collection", json={"collection_id": str(other_collection.id)}
    )

    assert response.status_code == 404


def test_set_active_collection_succeeds_for_a_member(logged_in_client, db):
    client, user = logged_in_client
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.flush()
    db.add(CollectionMember(user_id=user.id, collection_id=collection.id))
    db.commit()

    response = client.put("/mcp/active-collection", json={"collection_id": str(collection.id)})

    assert response.status_code == 200
    assert response.json() == {
        "collection_id": str(collection.id),
        "collection_name": "Doe Estate",
    }


def test_set_active_collection_can_be_cleared(logged_in_client, db):
    client, user = logged_in_client
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.flush()
    db.add(CollectionMember(user_id=user.id, collection_id=collection.id))
    db.commit()
    client.put("/mcp/active-collection", json={"collection_id": str(collection.id)})

    response = client.put("/mcp/active-collection", json={"collection_id": None})

    assert response.status_code == 200
    assert response.json() == {"collection_id": None, "collection_name": None}


def test_only_one_collection_can_be_active_at_once(logged_in_client, db):
    client, user = logged_in_client
    first = Collection(name="Doe Estate")
    second = Collection(name="Smith v. Jones")
    db.add_all([first, second])
    db.flush()
    db.add(CollectionMember(user_id=user.id, collection_id=first.id))
    db.add(CollectionMember(user_id=user.id, collection_id=second.id))
    db.commit()

    client.put("/mcp/active-collection", json={"collection_id": str(first.id)})
    response = client.put("/mcp/active-collection", json={"collection_id": str(second.id)})

    assert response.json()["collection_id"] == str(second.id)
    # the singleton row holds exactly one value -- activating the second
    # collection necessarily deactivated the first, there's no "both active"
    # state to assert against separately
    get_response = client.get("/mcp/active-collection")
    assert get_response.json()["collection_id"] == str(second.id)
