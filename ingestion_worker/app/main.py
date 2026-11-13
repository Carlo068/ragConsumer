from fastapi import FastAPI

from app import queue
from app.config import settings
from app.pipeline import _engine, process_document

app = FastAPI()

runner = queue.Runner(
    _engine,
    process_document,
    poll_seconds=settings.QUEUE_POLL_SECONDS,
    stuck_after_minutes=settings.STUCK_AFTER_MINUTES,
)


@app.on_event("startup")
def on_startup() -> None:
    # Anything caught mid-file by a restart goes back in the queue.
    requeued = queue.requeue_interrupted(_engine)
    if requeued:
        print(f"Re-queued {requeued} document(s) interrupted by a restart")
    runner.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    runner.stop()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook():
    """Storage tells us something was uploaded. We don't trust or even read the
    event: the documents table is the queue, so this just wakes the worker and
    answers straight away, however slow processing is. (A dropped or early
    event is harmless: the worker also polls.)"""
    runner.wake()
    return {"ok": True}
