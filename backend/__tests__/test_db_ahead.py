from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from scripts.db_ahead import database_is_ahead

HEAD = "e51a9c3d7f20"  # any revision this code knows


def engine_with(revision):
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    if revision is not None:
        with engine.begin() as c:
            c.execute(text("create table alembic_version (version_num varchar(32) not null)"))
            c.execute(text("insert into alembic_version values (:r)"), {"r": revision})
    return engine


def test_unknown_revision_means_the_database_is_ahead():
    assert database_is_ahead(engine_with("ffffffffffff")) is True


def test_a_revision_this_code_knows_is_not_ahead():
    assert database_is_ahead(engine_with(HEAD)) is False


def test_no_version_table_is_not_ahead():
    assert database_is_ahead(engine_with(None)) is False


def test_empty_version_table_is_not_ahead():
    engine = engine_with("x")
    with engine.begin() as c:
        c.execute(text("delete from alembic_version"))
    assert database_is_ahead(engine) is False
