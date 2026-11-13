from urllib.parse import unquote_plus

from fastapi import FastAPI, Request

from app.pipeline import process_object

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    for record in body.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        try:
            process_object(bucket, key)
        except Exception as exc:  # noqa: BLE001 - one bad record shouldn't 500 the whole webhook
            print(f"Failed to process {key}: {exc}")
    return {"ok": True}
