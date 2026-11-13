"""Rebuild every matter's search index.

Needed once after the search models change (DENSE_MODEL / BM25_LANGUAGE in the
worker and the MCP server), because vectors made by different models cannot be
mixed. Run inside the backend container, with the stack up:

    docker compose exec backend python scripts/reindex_all.py --yes

What it does: deletes every matter's Qdrant collection, then puts every document
back in the worker's queue. The worker re-reads each original file from storage
and indexes it again with the current models, so nothing is lost. If the worker
is interrupted it simply carries on (documents waiting are "uploaded").

While it runs, searches through the AI come back empty for matters that are not
rebuilt yet (the MCP server says the index is being rebuilt). Run it outside
working hours. Progress: documents move from "uploaded" to "ready".
"""

import argparse
import sys

from qdrant_client import QdrantClient
from sqlalchemy import create_engine, text

sys.path.insert(0, ".")
from app.config import settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="confirm: search is unavailable until the rebuild finishes")
    args = parser.parse_args()
    if not args.yes:
        print(__doc__)
        print("Nothing was changed. Run again with --yes to proceed.")
        return 1

    client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)
    names = [c.name for c in client.get_collections().collections if c.name.startswith("matter_")]
    for name in names:
        client.delete_collection(name)
    print(f"Deleted {len(names)} matter index collection(s).")

    engine = create_engine(settings.DATABASE_URL)
    with engine.begin() as conn:
        result = conn.execute(
            text("UPDATE documents SET status = 'uploaded', error_message = NULL, updated_at = now()")
        )
    print(f"Queued {result.rowcount} document(s) for re-indexing. The worker is on it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
