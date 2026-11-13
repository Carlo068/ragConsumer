from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from app.failures import NO_TEXT, TIMED_OUT, UNEXPECTED, UNREADABLE, NoTextFound, failure_reason
from app.queue import fail_stuck, Runner

NOW = datetime(2026, 11, 13, 12, 0, 0)


class UnsupportedFormatException(Exception):
    pass


class FileConversionException(Exception):
    pass


def test_an_empty_file_gets_the_no_text_code():
    assert failure_reason(NoTextFound()) == NO_TEXT == "no_text"


@pytest.mark.parametrize("error", [UnsupportedFormatException("x"), FileConversionException("x")])
def test_an_unreadable_file_gets_the_unreadable_explanation(error):
    assert failure_reason(error) == UNREADABLE


def test_anything_else_gets_a_generic_code_without_leaking_internals():
    reason = failure_reason(RuntimeError("/srv/secret/path.pdf: boom"))
    assert reason == UNEXPECTED == "unexpected"
    assert "secret" not in reason and "boom" not in reason


@pytest.fixture
def engine(tmp_path):
    # A file database (not :memory:), because the runner thread and the test
    # thread must not share one connection.
    engine = create_engine(f"sqlite:///{tmp_path / 'queue.db'}", connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE documents (id TEXT PRIMARY KEY, collection_id TEXT, object_key TEXT, "
                "source_filename TEXT, status TEXT, error_message TEXT, created_at TEXT, updated_at TEXT)"
            )
        )
    return engine


def add(engine, doc_id, status, updated):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO documents VALUES (:id, 'm1', 'k', 'f.pdf', :s, NULL, :u, :u)"),
            {"id": doc_id, "s": status, "u": updated.strftime("%Y-%m-%d %H:%M:%S")},
        )


def row(engine, doc_id):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT status, error_message FROM documents WHERE id = :id"), {"id": doc_id}
        ).one()


def test_a_document_processing_for_too_long_is_failed_with_a_reason(engine):
    add(engine, "stuck", "processing", NOW - timedelta(minutes=90))
    assert fail_stuck(engine, 60, now=NOW) == 1
    assert tuple(row(engine, "stuck")) == ("failed", TIMED_OUT)


def test_a_document_still_within_the_limit_is_left_alone(engine):
    add(engine, "busy", "processing", NOW - timedelta(minutes=10))
    assert fail_stuck(engine, 60, now=NOW) == 0
    assert row(engine, "busy")[0] == "processing"


def test_only_processing_documents_are_ever_timed_out(engine):
    for doc_id, status in (("w", "uploaded"), ("r", "ready"), ("f", "failed")):
        add(engine, doc_id, status, NOW - timedelta(days=3))
    assert fail_stuck(engine, 60, now=NOW) == 0
    assert [row(engine, d)[0] for d in "wrf"] == ["uploaded", "ready", "failed"]


def test_the_runner_clears_stuck_documents_on_its_own(engine):
    # Old enough that the real clock (used by the runner) also sees it as stuck.
    add(engine, "stuck", "processing", datetime(2020, 1, 1))
    runner = Runner(engine, lambda job: None, poll_seconds=0.05, stuck_after_minutes=60, log=lambda _: None)
    runner.start()
    import time

    deadline = time.time() + 3
    while time.time() < deadline and row(engine, "stuck")[0] != "failed":
        time.sleep(0.02)
    runner.stop()
    assert tuple(row(engine, "stuck")) == ("failed", TIMED_OUT)
