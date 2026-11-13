import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.matters import get_allowed_matters, matter_collection_name


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE collections (id TEXT PRIMARY KEY, name TEXT)"))
        conn.execute(text("CREATE TABLE collection_members (user_id TEXT, collection_id TEXT)"))
        conn.execute(text("CREATE TABLE ai_matter_selections (user_id TEXT, collection_id TEXT)"))
        for matter_id, name in (("m1", "Doe Estate"), ("m2", "Acme Dispute"), ("m3", "Secret Matter")):
            conn.execute(text("INSERT INTO collections VALUES (:i, :n)"), {"i": matter_id, "n": name})
    return engine


def member(engine, user, matter):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO collection_members VALUES (:u, :m)"), {"u": user, "m": matter})


def select(engine, user, matter):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO ai_matter_selections VALUES (:u, :m)"), {"u": user, "m": matter})


def test_nothing_selected_means_nothing_reachable(engine):
    member(engine, "ana", "m1")
    assert get_allowed_matters(engine, "ana") == {}


def test_a_selected_matter_the_person_belongs_to_is_reachable(engine):
    member(engine, "ana", "m1")
    select(engine, "ana", "m1")
    assert get_allowed_matters(engine, "ana") == {"m1": "Doe Estate"}


def test_being_a_member_alone_is_not_enough(engine):
    member(engine, "ana", "m1")
    member(engine, "ana", "m2")
    select(engine, "ana", "m1")
    assert list(get_allowed_matters(engine, "ana")) == ["m1"]


def test_a_removed_member_loses_the_matter_even_though_the_selection_remains(engine):
    member(engine, "ana", "m1")
    select(engine, "ana", "m1")
    assert get_allowed_matters(engine, "ana") == {"m1": "Doe Estate"}

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM collection_members WHERE user_id='ana' AND collection_id='m1'"))
    assert get_allowed_matters(engine, "ana") == {}


def test_a_selection_for_a_matter_never_joined_grants_nothing(engine):
    # E.g. a stale or forged row: selecting is not the same as being allowed.
    select(engine, "ana", "m3")
    assert get_allowed_matters(engine, "ana") == {}


def test_someone_elses_selection_and_membership_never_leak_across_people(engine):
    member(engine, "ana", "m1")
    select(engine, "ana", "m1")
    member(engine, "beto", "m3")
    select(engine, "beto", "m3")
    assert get_allowed_matters(engine, "ana") == {"m1": "Doe Estate"}
    assert get_allowed_matters(engine, "beto") == {"m3": "Secret Matter"}
    assert get_allowed_matters(engine, "carla") == {}


def test_several_matters_come_back_sorted_by_name(engine):
    for matter in ("m1", "m2"):
        member(engine, "ana", matter)
        select(engine, "ana", matter)
    assert list(get_allowed_matters(engine, "ana").values()) == ["Acme Dispute", "Doe Estate"]


def test_qdrant_collection_naming_matches_the_other_services():
    assert matter_collection_name("abc") == "matter_abc"
