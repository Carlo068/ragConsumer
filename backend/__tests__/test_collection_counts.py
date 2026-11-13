import pytest

from app.models import Collection, CollectionMember, CollectionRole, Document, DocumentStatus


@pytest.fixture
def two_matters(db, logged_in_client):
    client, user = logged_in_client
    busy = Collection(name="Busy")
    empty = Collection(name="Empty")
    other = Collection(name="Someone else's")
    db.add_all([busy, empty, other])
    db.flush()
    for matter in (busy, empty):
        db.add(CollectionMember(user_id=user.id, collection_id=matter.id, role=CollectionRole.owner))

    def doc(matter, status, name):
        db.add(
            Document(
                collection_id=matter.id, uploaded_by=user.id, source_filename=name,
                object_key=f"k/{name}", status=status,
            )
        )

    for i in range(3):
        doc(busy, DocumentStatus.ready, f"r{i}.pdf")
    doc(busy, DocumentStatus.failed, "f.pdf")
    doc(busy, DocumentStatus.uploaded, "u.pdf")
    doc(busy, DocumentStatus.processing, "p.pdf")
    for i in range(7):
        doc(other, DocumentStatus.ready, f"o{i}.pdf")  # not visible to this user
    db.commit()
    return client


def test_each_matter_reports_its_file_counts(two_matters):
    rows = {r["name"]: r for r in two_matters.get("/collections").json()}
    assert (rows["Busy"]["document_count"], rows["Busy"]["ready_count"], rows["Busy"]["failed_count"]) == (6, 3, 1)


def test_a_matter_without_files_reports_zeros(two_matters):
    rows = {r["name"]: r for r in two_matters.get("/collections").json()}
    assert (rows["Empty"]["document_count"], rows["Empty"]["ready_count"], rows["Empty"]["failed_count"]) == (0, 0, 0)


def test_counts_never_include_matters_the_person_cannot_see(two_matters):
    names = {r["name"] for r in two_matters.get("/collections").json()}
    assert names == {"Busy", "Empty"}


def test_a_renamed_matter_still_reports_its_counts(two_matters):
    matter_id = next(r["id"] for r in two_matters.get("/collections").json() if r["name"] == "Busy")
    body = two_matters.patch(f"/collections/{matter_id}", json={"name": "Busy 2"}).json()
    assert body["document_count"] == 6 and body["ready_count"] == 3
