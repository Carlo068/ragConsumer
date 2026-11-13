import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import Collection, CollectionMember, CollectionRole

OWNER, EDITOR, VIEWER = CollectionRole.owner, CollectionRole.editor, CollectionRole.viewer


@pytest.fixture
def matter(db):
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.commit()
    return collection


@pytest.fixture
def join(db, matter, make_user):
    """join('ana@firm.mx', OWNER) -> user, as a member of the matter."""

    def _join(email, role):
        user = make_user(email=email)
        db.add(CollectionMember(user_id=user.id, collection_id=matter.id, role=role))
        db.commit()
        return user

    return _join


def _client_for(user):
    client = TestClient(app)
    client.__enter__()
    assert client.post(
        "/auth/login", json={"email": user.email, "password": "password123"}
    ).status_code == 200
    return client


def _members(client, matter):
    return {m["email"]: m["role"] for m in client.get(f"/collections/{matter.id}/members").json()}


# --- Who can see the list ----------------------------------------------------


@pytest.mark.parametrize("role", [OWNER, EDITOR, VIEWER])
def test_any_member_can_see_who_is_on_the_matter(role, join, matter):
    me = join("me@firm.mx", role)
    join("other@firm.mx", OWNER)
    assert set(_members(_client_for(me), matter)) == {"me@firm.mx", "other@firm.mx"}


def test_a_non_member_cannot_see_the_list(make_user, matter, join):
    join("owner@firm.mx", OWNER)
    outsider = make_user(email="outsider@firm.mx")
    assert _client_for(outsider).get(f"/collections/{matter.id}/members").status_code == 404


# --- Adding ----------------------------------------------------------------


def test_owner_can_add_an_existing_user_with_a_chosen_role(join, matter, make_user):
    owner = join("owner@firm.mx", OWNER)
    make_user(email="nueva@firm.mx")
    client = _client_for(owner)
    response = client.post(
        f"/collections/{matter.id}/members", json={"email": "Nueva@Firm.mx", "role": "viewer"}
    )
    assert response.status_code == 201
    assert response.json()["role"] == "viewer"
    assert _members(client, matter)["nueva@firm.mx"] == "viewer"


@pytest.mark.parametrize("role", [EDITOR, VIEWER])
def test_only_owners_can_add_members(role, join, matter, make_user):
    me = join("me@firm.mx", role)
    make_user(email="nueva@firm.mx")
    response = _client_for(me).post(
        f"/collections/{matter.id}/members", json={"email": "nueva@firm.mx", "role": "viewer"}
    )
    assert response.status_code == 403


def test_cannot_add_someone_without_an_account(join, matter):
    owner = join("owner@firm.mx", OWNER)
    response = _client_for(owner).post(
        f"/collections/{matter.id}/members", json={"email": "ghost@firm.mx", "role": "viewer"}
    )
    assert response.status_code == 404
    assert "administrator" in response.json()["detail"]


def test_cannot_add_the_same_person_twice(join, matter):
    owner = join("owner@firm.mx", OWNER)
    join("dup@firm.mx", VIEWER)
    response = _client_for(owner).post(
        f"/collections/{matter.id}/members", json={"email": "dup@firm.mx", "role": "editor"}
    )
    assert response.status_code == 409


def test_an_invalid_role_is_rejected(join, matter, make_user):
    owner = join("owner@firm.mx", OWNER)
    make_user(email="nueva@firm.mx")
    response = _client_for(owner).post(
        f"/collections/{matter.id}/members", json={"email": "nueva@firm.mx", "role": "superuser"}
    )
    assert response.status_code == 422


# --- Changing roles --------------------------------------------------------


def test_owner_can_change_a_role(join, matter):
    owner = join("owner@firm.mx", OWNER)
    target = join("t@firm.mx", VIEWER)
    client = _client_for(owner)
    response = client.patch(f"/collections/{matter.id}/members/{target.id}", json={"role": "editor"})
    assert response.status_code == 200 and response.json()["role"] == "editor"


@pytest.mark.parametrize("role", [EDITOR, VIEWER])
def test_non_owners_cannot_change_roles_including_their_own(role, join, matter):
    """No promoting yourself: that's the whole point of the role."""
    me = join("me@firm.mx", role)
    client = _client_for(me)
    response = client.patch(f"/collections/{matter.id}/members/{me.id}", json={"role": "owner"})
    assert response.status_code == 403


def test_the_last_owner_cannot_be_demoted(join, matter):
    owner = join("owner@firm.mx", OWNER)
    response = _client_for(owner).patch(
        f"/collections/{matter.id}/members/{owner.id}", json={"role": "viewer"}
    )
    assert response.status_code == 409


def test_an_owner_can_step_down_when_another_owner_exists(join, matter):
    first = join("a@firm.mx", OWNER)
    join("b@firm.mx", OWNER)
    response = _client_for(first).patch(
        f"/collections/{matter.id}/members/{first.id}", json={"role": "editor"}
    )
    assert response.status_code == 200


def test_changing_the_role_of_a_non_member_is_404(join, matter, make_user):
    owner = join("owner@firm.mx", OWNER)
    stranger = make_user(email="stranger@firm.mx")
    response = _client_for(owner).patch(
        f"/collections/{matter.id}/members/{stranger.id}", json={"role": "viewer"}
    )
    assert response.status_code == 404


# --- Removing --------------------------------------------------------------


def test_owner_can_remove_a_member_and_they_lose_access_immediately(join, matter):
    owner = join("owner@firm.mx", OWNER)
    target = join("t@firm.mx", EDITOR)
    target_client = _client_for(target)
    assert target_client.get(f"/collections/{matter.id}/documents").status_code == 200

    assert _client_for(owner).delete(f"/collections/{matter.id}/members/{target.id}").status_code == 204
    assert target_client.get(f"/collections/{matter.id}/documents").status_code == 404


@pytest.mark.parametrize("role", [EDITOR, VIEWER])
def test_non_owners_cannot_remove_others(role, join, matter):
    me = join("me@firm.mx", role)
    other = join("other@firm.mx", VIEWER)
    response = _client_for(me).delete(f"/collections/{matter.id}/members/{other.id}")
    assert response.status_code == 403


@pytest.mark.parametrize("role", [EDITOR, VIEWER])
def test_anyone_can_leave_a_matter_themselves(role, join, matter, db):
    join("owner@firm.mx", OWNER)
    me = join("me@firm.mx", role)
    assert _client_for(me).delete(f"/collections/{matter.id}/members/{me.id}").status_code == 204
    assert db.scalar(select(CollectionMember).where(CollectionMember.user_id == me.id)) is None


def test_the_last_owner_cannot_leave_or_be_removed(join, matter):
    owner = join("owner@firm.mx", OWNER)
    assert _client_for(owner).delete(f"/collections/{matter.id}/members/{owner.id}").status_code == 409


def test_a_removed_owner_is_allowed_when_another_owner_remains(join, matter):
    first = join("a@firm.mx", OWNER)
    second = join("b@firm.mx", OWNER)
    assert _client_for(first).delete(f"/collections/{matter.id}/members/{second.id}").status_code == 204


def test_removal_on_one_matter_does_not_touch_another(join, matter, db, make_user):
    owner = join("owner@firm.mx", OWNER)
    target = join("t@firm.mx", EDITOR)
    other = Collection(name="Other matter")
    db.add(other)
    db.flush()
    db.add(CollectionMember(user_id=target.id, collection_id=other.id, role=EDITOR))
    db.commit()
    _client_for(owner).delete(f"/collections/{matter.id}/members/{target.id}")
    still = db.scalar(
        select(CollectionMember).where(
            CollectionMember.user_id == target.id, CollectionMember.collection_id == other.id
        )
    )
    assert still is not None


def test_admin_gets_no_way_into_a_matter_through_this_api(make_user, matter, join):
    """Ethical walls: even a firm admin can't list or alter a matter's members."""
    join("owner@firm.mx", OWNER)
    admin = make_user(email="admin@firm.mx", is_admin=True)
    client = _client_for(admin)
    assert client.get(f"/collections/{matter.id}/members").status_code == 404
    assert client.post(
        f"/collections/{matter.id}/members", json={"email": "admin@firm.mx", "role": "owner"}
    ).status_code == 404
