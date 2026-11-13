"""One-off migration: split the old shared Qdrant collection "chunks" into one
collection per matter ("matter_<id>").

Points are copied with their stored vectors, so nothing is re-embedded and it
is fast. It is safe to run more than once: point ids are unchanged, so a rerun
just overwrites the same points.

    python scripts/migrate_qdrant_per_matter.py            # copy, keep old collection
    python scripts/migrate_qdrant_per_matter.py --drop-old # copy, verify, then delete "chunks"

Points whose matter no longer exists in Postgres are reported and skipped.
"""

import argparse
import sys
from collections import defaultdict

from qdrant_client import QdrantClient, models
from sqlalchemy import create_engine, text

sys.path.insert(0, ".")
from app.config import settings  # noqa: E402

OLD_COLLECTION = "chunks"
DENSE_VECTOR_SIZE = 384
BATCH = 256


def matter_collection_name(collection_id: str) -> str:
    return f"matter_{collection_id}"


def ensure_matter_collection(client: QdrantClient, name: str) -> None:
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config={
                "dense": models.VectorParams(size=DENSE_VECTOR_SIZE, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={"sparse": models.SparseVectorParams()},
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drop-old", action="store_true", help="delete 'chunks' after a verified copy")
    args = parser.parse_args()

    client = QdrantClient(url=settings.QDRANT_URL)
    if not client.collection_exists(OLD_COLLECTION):
        print(f"No '{OLD_COLLECTION}' collection: nothing to migrate.")
        return 0

    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        known = {str(row[0]) for row in conn.execute(text("SELECT id FROM collections"))}

    copied: dict[str, int] = defaultdict(int)
    orphans = 0
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=OLD_COLLECTION,
            limit=BATCH,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        by_matter: dict[str, list[models.PointStruct]] = defaultdict(list)
        for point in points:
            matter_id = (point.payload or {}).get("collection_id")
            if matter_id not in known:
                orphans += 1
                continue
            by_matter[matter_id].append(
                models.PointStruct(id=point.id, vector=point.vector, payload=point.payload)
            )
        for matter_id, batch in by_matter.items():
            name = matter_collection_name(matter_id)
            ensure_matter_collection(client, name)
            client.upsert(collection_name=name, points=batch)
            copied[matter_id] += len(batch)
        if offset is None:
            break

    for matter_id, count in sorted(copied.items()):
        print(f"  matter {matter_id}: {count} chunks")
    print(f"Copied {sum(copied.values())} chunks into {len(copied)} matter collections; "
          f"skipped {orphans} orphaned chunks.")

    if args.drop_old:
        # Verify before deleting anything: every matter collection must hold at
        # least as many points as were copied into it.
        for matter_id, count in copied.items():
            have = client.count(collection_name=matter_collection_name(matter_id), exact=True).count
            if have < count:
                print(f"Verification failed for matter {matter_id} ({have} < {count}); keeping '{OLD_COLLECTION}'.")
                return 1
        client.delete_collection(OLD_COLLECTION)
        print(f"Verified and deleted the old '{OLD_COLLECTION}' collection.")
    else:
        print(f"Kept the old '{OLD_COLLECTION}' collection. Rerun with --drop-old once you have checked the result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
