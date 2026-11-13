import threading
import time

import pytest
from sqlalchemy import create_engine, text

from app.queue import Runner, claim_next, requeue_interrupted


@pytest.fixture
def engine(tmp_path):
    # A file database (not :memory:), because the runner thread and the test
    # thread must not share one connection.
    engine = create_engine(f"sqlite:///{tmp_path / 'queue.db'}", connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE documents (id TEXT PRIMARY KEY, collection_id TEXT, object_key TEXT, "
                "source_filename TEXT, status TEXT, created_at TEXT, updated_at TEXT)"
            )
        )
    return engine


def add(engine, doc_id, status="uploaded", created="2026-11-13 09:00:00"):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO documents VALUES (:id, 'm1', :key, :name, :status, :created, :created)"),
            {"id": doc_id, "key": f"collection-m1/doc-{doc_id}/{doc_id}.pdf", "name": f"{doc_id}.pdf",
             "status": status, "created": created},
        )


def status_of(engine, doc_id):
    with engine.connect() as conn:
        return conn.execute(text("SELECT status FROM documents WHERE id = :id"), {"id": doc_id}).scalar()


def test_nothing_pending_means_no_job(engine):
    add(engine, "a", status="ready")
    assert claim_next(engine) is None


def test_the_oldest_pending_document_is_taken_first_and_marked_processing(engine):
    add(engine, "newer", created="2026-11-13 10:00:00")
    add(engine, "older", created="2026-11-13 08:00:00")
    job = claim_next(engine)
    assert job.doc_id == "older" and job.collection_id == "m1" and job.filename == "older.pdf"
    assert status_of(engine, "older") == "processing"
    assert status_of(engine, "newer") == "uploaded"


def test_a_document_can_only_be_taken_once(engine):
    add(engine, "a")
    assert claim_next(engine).doc_id == "a"
    assert claim_next(engine) is None


def test_documents_interrupted_by_a_restart_go_back_in_the_queue(engine):
    add(engine, "stuck", status="processing")
    add(engine, "done", status="ready")
    add(engine, "broken", status="failed")
    assert requeue_interrupted(engine) == 1
    assert status_of(engine, "stuck") == "uploaded"
    assert status_of(engine, "done") == "ready" and status_of(engine, "broken") == "failed"
    assert claim_next(engine).doc_id == "stuck"


def run_until(runner, condition, timeout=5):
    runner.start()
    deadline = time.time() + timeout
    while time.time() < deadline and not condition():
        time.sleep(0.02)
    runner.stop()


def test_the_runner_works_through_everything_pending(engine):
    for name in ("a", "b", "c"):
        add(engine, name, created=f"2026-11-13 09:00:0{ord(name) - 96}")
    done = []
    runner = Runner(engine, lambda job: done.append(job.doc_id), poll_seconds=0.05)
    run_until(runner, lambda: len(done) == 3)
    assert done == ["a", "b", "c"]


def test_one_failing_file_does_not_stop_the_others(engine):
    add(engine, "bad", created="2026-11-13 09:00:01")
    add(engine, "good", created="2026-11-13 09:00:02")
    done, logs = [], []

    def process(job):
        if job.doc_id == "bad":
            raise RuntimeError("corrupt file")
        done.append(job.doc_id)

    runner = Runner(engine, process, poll_seconds=0.05, log=logs.append)
    run_until(runner, lambda: done == ["good"])
    assert done == ["good"]
    assert any("corrupt file" in line for line in logs)


def test_a_document_added_later_is_found_without_any_webhook(engine):
    done = []
    runner = Runner(engine, lambda job: done.append(job.doc_id), poll_seconds=0.05)
    runner.start()
    time.sleep(0.15)
    add(engine, "late")  # no wake() call: the poll must find it
    deadline = time.time() + 5
    while time.time() < deadline and not done:
        time.sleep(0.02)
    runner.stop()
    assert done == ["late"]


def test_waking_the_runner_picks_up_work_before_the_next_poll(engine):
    done = []
    runner = Runner(engine, lambda job: done.append(job.doc_id), poll_seconds=30)
    runner.start()
    time.sleep(0.1)
    add(engine, "now")
    runner.wake()
    deadline = time.time() + 3
    while time.time() < deadline and not done:
        time.sleep(0.02)
    runner.stop()
    assert done == ["now"]


def test_a_slow_file_never_blocks_the_caller(engine):
    """The webhook only calls wake(); it must return at once even while a
    document is being processed."""
    add(engine, "slow")
    started, release = threading.Event(), threading.Event()

    def process(job):
        started.set()
        release.wait(5)

    runner = Runner(engine, process, poll_seconds=0.05)
    runner.start()
    assert started.wait(3)
    t0 = time.time()
    runner.wake()
    assert time.time() - t0 < 0.1
    release.set()
    runner.stop()
