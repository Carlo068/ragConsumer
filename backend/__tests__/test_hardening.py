import pytest
from sqlalchemy import select

from app import audit
from app.models import AuditLog, Collection, CollectionMember, CollectionRole, Document
from app.routers.documents import MAX_FILENAME_LENGTH, safe_filename


# ---- filenames ----

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("contrato.pdf", "contrato.pdf"),
        ("Demanda de amparo — final.docx", "Demanda de amparo — final.docx"),
        ("../../etc/passwd", "etc/passwd"),
        ("a/b/c.pdf", "a/b/c.pdf"),
        ("C:" + chr(92) + "Users" + chr(92) + "ana" + chr(92) + "acta.pdf", "C:/Users/ana/acta.pdf"),
        (".hidden.pdf", "hidden.pdf"),
        ("bad" + chr(0) + "name" + chr(10) + ".pdf", "badname.pdf"),
        ("  spaced.pdf  ", "spaced.pdf"),
    ],
)
def test_safe_filename_strips_directories_and_control_characters(raw, expected):
    assert safe_filename(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "..", "/", "...", "../..", "./."])
def test_safe_filename_rejects_names_with_nothing_left(raw):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        safe_filename(raw)
    assert error.value.status_code == 400


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("contratos/2024/arrendamiento.pdf", "contratos/2024/arrendamiento.pdf"),
        ("contratos//2024/./arrendamiento.pdf", "contratos/2024/arrendamiento.pdf"),
        ("/contratos/2024/", "contratos/2024"),
        ("  contratos  /  2024  /a.pdf", "contratos/2024/a.pdf"),
        ("a/../b/.hidden/c.pdf", "a/b/hidden/c.pdf"),
    ],
)
def test_folders_are_kept_in_the_name_and_cleaned_segment_by_segment(raw, expected):
    assert safe_filename(raw) == expected


def test_a_path_can_never_climb_out_of_the_documents_own_folder():
    for raw in ("../../../x.pdf", "a/../../x.pdf", "/../x.pdf", "..///x.pdf"):
        name = safe_filename(raw)
        assert ".." not in name.split("/") and not name.startswith("/")


def test_very_deep_folders_keep_the_file_and_its_nearest_folders():
    name = safe_filename("/".join(f"d{i}" for i in range(30)) + "/acta.pdf")
    assert name.endswith("d29/acta.pdf") and len(name.split("/")) == 12


def test_a_long_filename_is_shortened_but_keeps_its_extension():
    result = safe_filename("x" * 700 + ".pdf")
    assert len(result) == MAX_FILENAME_LENGTH and result.endswith(".pdf")


def test_a_very_long_filename_no_longer_breaks_the_upload(logged_in_client, db, monkeypatch):
    client, user = logged_in_client
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.flush()
    db.add(CollectionMember(user_id=user.id, collection_id=collection.id, role=CollectionRole.owner))
    db.commit()
    stored = []
    monkeypatch.setattr(
        "app.routers.documents.minio_client.put_object", lambda bucket, key, *a, **k: stored.append(key)
    )

    response = client.post(
        f"/collections/{collection.id}/documents",
        files={"file": ("y" * 700 + ".pdf", b"x", "application/pdf")},
    )

    assert response.status_code == 201
    assert len(response.json()["source_filename"]) == MAX_FILENAME_LENGTH
    assert len(stored) == 1 and stored[0].endswith(".pdf")


def test_a_file_uploaded_from_a_folder_keeps_its_path_and_stays_inside_its_own_storage_folder(
    logged_in_client, db, monkeypatch
):
    client, user = logged_in_client
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.flush()
    db.add(CollectionMember(user_id=user.id, collection_id=collection.id, role=CollectionRole.owner))
    db.commit()
    stored = []
    monkeypatch.setattr(
        "app.routers.documents.minio_client.put_object", lambda bucket, key, *a, **k: stored.append(key)
    )

    response = client.post(
        f"/collections/{collection.id}/documents",
        files={"file": ("../contratos/2024/arrendamiento.pdf", b"x", "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json()["source_filename"] == "contratos/2024/arrendamiento.pdf"
    [key] = stored
    assert key.startswith(f"collection-{collection.id}/doc-")
    assert key.endswith("/contratos/2024/arrendamiento.pdf") and ".." not in key.split("/")


def test_an_upload_that_fails_to_save_takes_its_file_back_out_of_storage(
    logged_in_client, db, monkeypatch
):
    client, user = logged_in_client
    collection = Collection(name="Doe Estate")
    db.add(collection)
    db.flush()
    db.add(CollectionMember(user_id=user.id, collection_id=collection.id, role=CollectionRole.owner))
    db.commit()
    stored, removed = [], []
    monkeypatch.setattr(
        "app.routers.documents.minio_client.put_object", lambda bucket, key, *a, **k: stored.append(key)
    )
    monkeypatch.setattr("app.routers.documents.delete_object", removed.append)

    def explode(*args, **kwargs):
        raise RuntimeError("database down")

    monkeypatch.setattr("app.routers.documents.audit.record", explode)
    with pytest.raises(RuntimeError):
        client.post(
            f"/collections/{collection.id}/documents",
            files={"file": ("a.pdf", b"x", "application/pdf")},
        )

    # No row, and the stored object was removed so it can't be indexed unseen.
    assert removed == stored
    db.expire_all()
    assert db.scalars(select(Document)).all() == []


# ---- login ----

def test_login_does_the_same_password_work_for_unknown_emails(client, make_user, monkeypatch):
    """An unknown email must still pay for one password verification, or the
    response time reveals which emails have accounts."""
    calls = []
    real = __import__("app.routers.auth", fromlist=["verify_password"]).verify_password

    def spy(password, password_hash):
        calls.append(password_hash)
        return real(password, password_hash)

    monkeypatch.setattr("app.routers.auth.verify_password", spy)
    make_user("ana@firm.mx")
    client.post("/auth/login", json={"email": "ana@firm.mx", "password": "wrong-password-1"})
    client.post("/auth/login", json={"email": "nobody@firm.mx", "password": "wrong-password-1"})
    assert len(calls) == 2


def test_an_enormous_password_is_rejected_before_any_hashing(client):
    response = client.post(
        "/auth/login", json={"email": "ana@firm.mx", "password": "x" * 100_000}
    )
    assert response.status_code == 422


def test_an_enormous_password_cannot_be_set_through_an_invitation(admin_client):
    client, _ = admin_client
    created = client.post("/admin/invites", json={"email": "new@firm.mx"}).json()
    token = created["invite_url"].rsplit("/", 1)[1]
    response = client.post(f"/invites/{token}/accept", json={"password": "x" * 100_000})
    assert response.status_code == 422


# ---- session cookie ----

def test_the_session_cookie_settings_come_from_configuration():
    from app.config import settings
    from app.main import app

    middleware = {m.cls.__name__: m.kwargs for m in app.user_middleware}["SessionMiddleware"]
    assert middleware["https_only"] == settings.SESSION_HTTPS_ONLY
    assert middleware["max_age"] == settings.SESSION_MAX_AGE_HOURS * 3600
    assert middleware["same_site"] == "lax"


# ---- auditing the auditors ----

def test_opening_and_downloading_the_log_are_themselves_logged(admin_client, db):
    client, admin = admin_client
    client.get("/admin/audit")
    client.get("/admin/audit", params={"offset": 25})  # paging is not logged again
    client.get("/admin/audit.csv", params={"action": "login"})

    db.expire_all()
    viewed = db.scalars(select(AuditLog).where(AuditLog.action == audit.AUDIT_VIEWED)).all()
    exported = db.scalars(select(AuditLog).where(AuditLog.action == audit.AUDIT_EXPORTED)).all()
    assert len(viewed) == 1 and viewed[0].actor_email == admin.email
    assert len(exported) == 1 and exported[0].detail == {"action": "login"}
