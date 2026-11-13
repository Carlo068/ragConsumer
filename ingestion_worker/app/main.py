from fastapi import FastAPI, HTTPException, Request

from app import queue
from app.config import settings
from app.pipeline import _engine, process_document
from app.webhook_auth import webhook_authorized

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
async def webhook(request: Request):
    """Storage tells us something was uploaded. We don't trust or even read the
    event: the documents table is the queue, so this just wakes the worker and
    answers straight away, however slow processing is. (A dropped or early
    event is harmless: the worker also polls.) Only the storage service, which
    carries the shared token, may call it."""
    if not webhook_authorized(request.headers.get("authorization"), settings.WEBHOOK_TOKEN):
        print("Refused a webhook call without the right token")
        raise HTTPException(status_code=401, detail="Unauthorized")
    runner.wake()
    return {"ok": True}
