import pytest
from fastapi import HTTPException

from app.auth import require_collection_membership
from app.models import Collection, CollectionMember


def test_member_passes_silently(db, make_user):
    user = make_user()
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.flush()
    db.add(CollectionMember(user_id=user.id, collection_id=collection.id))
    db.commit()

    require_collection_membership(db, user.id, collection.id)  # does not raise


def test_non_member_raises_404_not_403(db, make_user):
    """404, not 403 -- the response shouldn't reveal whether the collection
    exists at all to someone who isn't a member of it."""
    user = make_user()
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        require_collection_membership(db, user.id, collection.id)

    assert exc_info.value.status_code == 404
