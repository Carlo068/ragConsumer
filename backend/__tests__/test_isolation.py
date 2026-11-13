"""Matter isolation, proven for every route at once.

The sweep reads the API's own route list, so a matter-scoped endpoint added
later is covered automatically, or fails here until someone decides what its
request should look like.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models import (
    AiMatterSelection,
    ApiToken,
    Collection,
    CollectionMember,
    CollectionRole,
    Document,
)

NO_BODY = {}
# Minimal valid requests, so a 404 can only mean "you can't see this matter",
# never "your request was malformed".
REQUEST_KWARGS = {
    ("POST", "/collections/{collection_id}/documents"): {
        "files": {"file": ("a.pdf", b"x", "application/pdf")}
    },
    ("POST", "/collections/{collection_id}/members"): {
        "json": {"email": "someone@firm.mx", "role": "viewer"}
    },
    ("POST", "/collections/{collection_id}/documents/{document_id}/reingest"): {},
    ("PATCH", "/collections/{collection_id}"): {"json": {"name": "Hijacked"}},
    ("PATCH", "/collections/{collection_id}/members/{user_id}"): {"json": {"role": "owner"}},
}


def matter_routes(client):
    paths = client.app.openapi()["paths"]
    return sorted(
        (method.upper(), path)
        for path, operations in paths.items()
        if "{collection_id}" in path
        for method in operations
    )


@pytest.fixture
def secret_matter(db, make_user):
    """A matter with an owner, a member and a document, none of whom is the
    person we test with."""
    owner = make_user("owner@firm.mx")
    collection = Collection(name="Confidential Client")
    db.add(collection)
    db.flush()
    db.add(CollectionMember(user_id=owner.id, collection_id=collection.id, role=CollectionRole.owner))
    document = Document(
        collection_id=collection.id,
        uploaded_by=owner.id,
        source_filename="secret.pdf",
        object_key="collection-x/doc-y/secret.pdf",
    )
    db.add(document)
    db.commit()
    return collection, owner, document


def call(client, method, template, collection, owner, document):
    path = (
        template.replace("{collection_id}", str(collection.id))
        .replace("{document_id}", str(document.id))
        .replace("{user_id}", str(owner.id))
    )
    return client.request(method, path, **REQUEST_KWARGS.get((method, template), {}))


def login(client, email, password="password123"):
    client.post("/auth/logout")
    assert client.post("/auth/login", json={"email": email, "password": password}).status_code == 200


def test_the_sweep_actually_finds_the_matter_routes(client):
    # Guards the guard: if route discovery silently returned nothing, every
    # parametrized check below would pass for the wrong reason.
    routes = matter_routes(client)
    assert len(routes) >= 11
    assert ("DELETE", "/collections/{collection_id}") in routes
    assert ("PUT", "/collections/{collection_id}/ai-access") in routes


def test_every_matter_route_that_takes_a_body_has_a_known_request(client):
    for method, template in matter_routes(client):
        if method in ("POST", "PATCH"):
            assert (method, template) in REQUEST_KWARGS, (
                f"{method} {template} needs an entry in REQUEST_KWARGS"
            )


def test_a_signed_out_visitor_is_refused_everywhere(client, secret_matter):
    collection, owner, document = secret_matter
    for method, template in matter_routes(client):
        response = call(client, method, template, collection, owner, document)
        assert response.status_code == 401, f"{method} {template} -> {response.status_code}"


def test_a_signed_in_stranger_gets_404_on_every_matter_route(client, make_user, secret_matter):
    collection, owner, document = secret_matter
    make_user("stranger@firm.mx")
    login(client, "stranger@firm.mx")
    for method, template in matter_routes(client):
        response = call(client, method, template, collection, owner, document)
        assert response.status_code == 404, f"{method} {template} -> {response.status_code}"
        # The refusal must not confirm that the matter exists or leak anything.
        assert "Confidential" not in response.text and "secret.pdf" not in response.text


def test_an_admin_without_a_role_is_just_a_stranger(client, make_user, secret_matter):
    collection, owner, document = secret_matter
    make_user("admin@firm.mx", is_admin=True)
    login(client, "admin@firm.mx")
    for method, template in matter_routes(client):
        response = call(client, method, template, collection, owner, document)
        assert response.status_code == 404, f"{method} {template} -> {response.status_code}"
    assert client.get("/collections").json() == []


def test_strangers_changes_never_reach_the_matter(client, make_user, secret_matter, db):
    collection, owner, document = secret_matter
    stranger = make_user("stranger@firm.mx")
    login(client, "stranger@firm.mx")
    for method, template in matter_routes(client):
        call(client, method, template, collection, owner, document)

    db.expire_all()
    assert db.get(Collection, collection.id).name == "Confidential Client"
    assert db.scalars(select(Document)).one().source_filename == "secret.pdf"
    members = db.scalars(select(CollectionMember)).all()
    assert [(m.user_id, m.role) for m in members] == [(owner.id, CollectionRole.owner)]
    assert db.scalars(select(AiMatterSelection)).all() == []
    assert stranger.id not in {m.user_id for m in members}


def test_a_removed_member_is_locked_out_of_every_route_at_once(client, make_user, secret_matter, db):
    collection, owner, document = secret_matter
    member = make_user("beto@firm.mx")
    db.add(CollectionMember(user_id=member.id, collection_id=collection.id, role=CollectionRole.owner))
    db.commit()

    login(client, "beto@firm.mx")
    assert client.get(f"/collections/{collection.id}/documents").status_code == 200

    # Removed by the other owner...
    login(client, "owner@firm.mx")
    assert client.delete(f"/collections/{collection.id}/members/{member.id}").status_code == 204

    # ...and the very next request from the removed person is refused everywhere,
    # with the same still-valid session.
    login_cookie_client = client
    login(login_cookie_client, "beto@firm.mx")
    for method, template in matter_routes(client):
        response = call(client, method, template, collection, owner, document)
        assert response.status_code == 404, f"{method} {template} -> {response.status_code}"


def test_one_persons_access_keys_are_invisible_to_everyone_else(client, make_user, db):
    ana = make_user("ana@firm.mx")
    make_user("beto@firm.mx")
    login(client, "ana@firm.mx")
    token_id = client.post("/tokens", json={"name": "Ana's laptop"}).json()["id"]

    login(client, "beto@firm.mx")
    assert client.get("/tokens").json() == []
    assert client.delete(f"/tokens/{token_id}").status_code == 404
    assert db.scalars(select(ApiToken)).one().user_id == ana.id
    assert db.scalars(select(ApiToken)).one().revoked_at is None


def test_the_audit_log_is_closed_to_everyone_but_admins(client, make_user, secret_matter):
    make_user("stranger@firm.mx")
    login(client, "stranger@firm.mx")
    assert client.get("/admin/audit").status_code == 403
    assert client.get("/admin/audit.csv").status_code == 403
    assert client.get("/admin/users").status_code == 403
    assert client.post("/admin/invites", json={"email": "x@firm.mx"}).status_code == 403


def test_unknown_matter_ids_look_exactly_like_forbidden_ones(client, make_user, secret_matter):
    collection, owner, document = secret_matter
    make_user("stranger@firm.mx")
    login(client, "stranger@firm.mx")
    real = client.get(f"/collections/{collection.id}/documents")
    missing = client.get(f"/collections/{uuid.uuid4()}/documents")
    assert (real.status_code, real.json()) == (missing.status_code, missing.json())
