"""A small durable job queue for ingestion, using the documents table itself.

A document whose status is "uploaded" is a pending job. The webhook from
storage only *wakes* the worker; it does not carry the work. So:

* the webhook can answer immediately, however slow a file is to process;
* a webhook that is dropped, arrives before the database row exists, or is
  never sent still gets picked up, because the loop also polls;
* jobs survive a worker restart (a document caught mid-processing is put back
  in the queue on startup).

Kept free of model and storage imports so it can be tested on its own.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class Job:
    doc_id: str
    collection_id: str
    object_key: str
    filename: str


def claim_next(engine: Engine) -> Job | None:
    """Take the oldest pending document, marking it as processing.

    The status change is conditional (only if it is still "uploaded"), so two
    workers can never take the same document.
    """
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT id, collection_id, object_key, source_filename FROM documents "
                "WHERE status = 'uploaded' ORDER BY created_at, id LIMIT 1"
            )
        ).first()
        if row is None:
            return None
        claimed = conn.execute(
            text(
                "UPDATE documents SET status = 'processing', updated_at = CURRENT_TIMESTAMP "
                "WHERE id = :id AND status = 'uploaded'"
            ),
            {"id": row[0]},
        )
        if claimed.rowcount != 1:
            return None  # someone else got it first; the loop will simply ask again
    return Job(doc_id=str(row[0]), collection_id=str(row[1]), object_key=row[2], filename=row[3])


def requeue_interrupted(engine: Engine) -> int:
    """Put documents left in "processing" (the worker died mid-file) back in
    the queue. Run once at startup, when nothing can really be processing."""
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE documents SET status = 'uploaded', updated_at = CURRENT_TIMESTAMP "
                "WHERE status = 'processing'"
            )
        )
    return result.rowcount


class Runner:
    """Background thread that works through the queue one document at a time."""

    def __init__(
        self,
        engine: Engine,
        process: Callable[[Job], None],
        poll_seconds: float = 10.0,
        log: Callable[[str], None] = print,
    ):
        self._engine = engine
        self._process = process
        self._poll_seconds = poll_seconds
        self._log = log
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="ingestion-queue", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)

    def wake(self) -> None:
        self._wake.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                job = claim_next(self._engine)
            except Exception as exc:  # noqa: BLE001 - the database may be briefly unavailable
                self._log(f"Could not read the queue: {exc}")
                job = None
            if job is not None:
                try:
                    self._process(job)
                except Exception as exc:  # noqa: BLE001 - one bad file must not stop the queue
                    self._log(f"Failed to process {job.object_key}: {exc}")
                continue  # more may be waiting: don't sleep between jobs
            self._wake.wait(self._poll_seconds)
            self._wake.clear()
