import json
import pathlib
import re

from app.models import Collection, CollectionMember, CollectionRole

APP = pathlib.Path(__file__).resolve().parents[1] / "app"


def source_files():
    return [p for p in APP.rglob("*.py") if p.name != "errors.py"]


def used_codes():
    codes = set()
    for path in source_files():
        for match in re.finditer(r"ApiError\(\s*[\w.]+\s*,\s*\"([a-z_]+)\"", path.read_text(encoding="utf-8")):
            codes.add(match.group(1))
    return codes


def test_every_code_used_is_listed_and_every_listed_code_is_used():
    listed = set(json.loads((APP / "error_codes.json").read_text(encoding="utf-8")))
    assert used_codes() == listed


def test_no_route_raises_a_bare_http_exception():
    # A bare HTTPException has no code, so the web app could only show raw English.
    for path in source_files():
        assert "raise HTTPException(" not in path.read_text(encoding="utf-8"), path.name


def test_a_failed_login_carries_its_code(client, make_user):
    make_user("ana@firm.mx")
    response = client.post("/auth/login", json={"email": "ana@firm.mx", "password": "wrong-password-1"})
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "invalid_credentials" and body["params"] == {}
    assert body["detail"] == "Invalid credentials"  # English stays for logs and API users


def test_signed_out_requests_carry_a_code(client):
    assert client.get("/collections").json()["code"] == "not_authenticated"


def test_a_stranger_gets_the_same_code_whether_or_not_the_matter_exists(client, make_user, db):
    make_user("ana@firm.mx")
    collection = Collection(name="Secret")
    db.add(collection)
    db.commit()
    client.post("/auth/login", json={"email": "ana@firm.mx", "password": "password123"})
    assert client.get(f"/collections/{collection.id}/documents").json()["code"] == "matter_not_found"


def test_a_role_error_names_the_role_needed(client, make_user, db):
    user = make_user("ana@firm.mx")
    collection = Collection(name="Doe")
    db.add(collection)
    db.flush()
    db.add(CollectionMember(user_id=user.id, collection_id=collection.id, role=CollectionRole.viewer))
    db.commit()
    client.post("/auth/login", json={"email": "ana@firm.mx", "password": "password123"})
    body = client.delete(f"/collections/{collection.id}").json()
    assert body["code"] == "role_required" and body["params"] == {"role": "owner"}


def test_the_upload_limit_error_carries_the_limit_for_the_message(logged_in_client, db, monkeypatch):
    client, user = logged_in_client
    collection = Collection(name="Doe")
    db.add(collection)
    db.flush()
    db.add(CollectionMember(user_id=user.id, collection_id=collection.id, role=CollectionRole.owner))
    db.commit()
    monkeypatch.setattr("app.config.settings.MAX_UPLOAD_MB", 1)
    response = client.post(
        f"/collections/{collection.id}/documents",
        files={"file": ("a.pdf", b"x" * (1024 * 1024 + 1), "application/pdf")},
    )
    assert response.status_code == 413
    assert response.json()["code"] == "file_too_large" and response.json()["params"] == {"max_mb": 1}
