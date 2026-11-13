import pytest
from sqlalchemy import select

from app.models import AiMatterSelection, Collection, CollectionMember, CollectionRole


@pytest.fixture
def matter(db):
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.commit()
    return collection


@pytest.fixture
def join(db, matter, make_user):
    def _join(email, role=CollectionRole.viewer):
        user = make_user(email=email)
        db.add(CollectionMember(user_id=user.id, collection_id=matter.id, role=role))
        db.commit()
        return user

    return _join


def login(client, email):
    client.post("/auth/logout")
    assert client.post("/auth/login", json={"email": email, "password": "password123"}).status_code == 200


def selections(db):
    db.expire_all()
    return {(s.user_id, s.collection_id) for s in db.scalars(select(AiMatterSelection))}


def test_nothing_is_selected_by_default(client, join, matter):
    join("ana@firm.mx")
    login(client, "ana@firm.mx")
    [row] = client.get("/collections").json()
    assert row["ai_enabled"] is False


@pytest.mark.parametrize("role", list(CollectionRole))
def test_any_member_can_turn_their_own_ai_on_and_off(client, join, matter, role):
    join("ana@firm.mx", role)
    login(client, "ana@firm.mx")

    assert client.put(f"/collections/{matter.id}/ai-access").status_code == 204
    assert client.get("/collections").json()[0]["ai_enabled"] is True

    assert client.delete(f"/collections/{matter.id}/ai-access").status_code == 204
    assert client.get("/collections").json()[0]["ai_enabled"] is False


def test_turning_it_on_twice_is_harmless(client, join, matter, db):
    ana = join("ana@firm.mx")
    login(client, "ana@firm.mx")
    assert client.put(f"/collections/{matter.id}/ai-access").status_code == 204
    assert client.put(f"/collections/{matter.id}/ai-access").status_code == 204
    assert selections(db) == {(ana.id, matter.id)}


def test_a_non_member_cannot_select_a_matter_and_cannot_tell_it_exists(
    client, make_user, matter, db
):
    make_user("outsider@firm.mx")
    login(client, "outsider@firm.mx")

    assert client.put(f"/collections/{matter.id}/ai-access").status_code == 404
    assert client.delete(f"/collections/{matter.id}/ai-access").status_code == 404
    assert selections(db) == set()


def test_requires_login(client, matter):
    assert client.put(f"/collections/{matter.id}/ai-access").status_code == 401


def test_my_choice_does_not_change_a_colleagues_ai(client, join, matter):
    """The old global toggle let one person's choice switch what everyone's AI
    could see. Selection is now per person."""
    join("ana@firm.mx")
    join("beto@firm.mx")

    login(client, "ana@firm.mx")
    client.put(f"/collections/{matter.id}/ai-access")

    login(client, "beto@firm.mx")
    assert client.get("/collections").json()[0]["ai_enabled"] is False


def test_leaving_a_matter_clears_the_selection(client, join, matter, db):
    ana = join("ana@firm.mx")
    join("owner@firm.mx", CollectionRole.owner)
    login(client, "ana@firm.mx")
    client.put(f"/collections/{matter.id}/ai-access")
    assert selections(db) == {(ana.id, matter.id)}

    assert client.delete(f"/collections/{matter.id}/members/{ana.id}").status_code == 204
    assert selections(db) == set()


def test_an_owner_removing_someone_clears_their_selection(client, join, matter, db):
    ana = join("ana@firm.mx")
    join("owner@firm.mx", CollectionRole.owner)
    login(client, "ana@firm.mx")
    client.put(f"/collections/{matter.id}/ai-access")

    login(client, "owner@firm.mx")
    assert client.delete(f"/collections/{matter.id}/members/{ana.id}").status_code == 204
    assert selections(db) == set()


def test_deleting_a_matter_clears_selections(client, join, matter, db, monkeypatch):
    monkeypatch.setattr("app.routers.collections.delete_matter_vectors", lambda _: None)
    monkeypatch.setattr("app.routers.collections.delete_objects_by_prefix", lambda _: None)
    owner = join("owner@firm.mx", CollectionRole.owner)
    login(client, "owner@firm.mx")
    client.put(f"/collections/{matter.id}/ai-access")
    assert selections(db) == {(owner.id, matter.id)}

    assert client.delete(f"/collections/{matter.id}").status_code == 204
    assert selections(db) == set()
