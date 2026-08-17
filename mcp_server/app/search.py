from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient, models
from sqlalchemy import create_engine, text

from app.config import settings

# Must match ingestion_worker/app/pipeline.py exactly -- same collection name,
# same vector names, same embedding models -- since this reads what that writes.
QDRANT_COLLECTION = "chunks"
DENSE_MODEL_NAME = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL_NAME = "Qdrant/bm25"

_qdrant_client = QdrantClient(url=settings.QDRANT_URL)
_dense_model = TextEmbedding(model_name=DENSE_MODEL_NAME)
_sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
_engine = create_engine(settings.DATABASE_URL)


def _collection_filter() -> models.FieldCondition:
    return models.FieldCondition(
        key="collection_id", match=models.MatchValue(value=settings.COLLECTION_ID)
    )


def search(query: str, limit: int = 5) -> list[dict]:
    dense_vec = list(_dense_model.embed([query]))[0]
    sparse_vec = list(_sparse_model.embed([query]))[0]

    results = _qdrant_client.query_points(
        collection_name=QDRANT_COLLECTION,
        prefetch=[
            models.Prefetch(query=dense_vec.tolist(), using="dense", limit=20),
            models.Prefetch(
                query=models.SparseVector(
                    indices=sparse_vec.indices.tolist(),
                    values=sparse_vec.values.tolist(),
                ),
                using="sparse",
                limit=20,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        query_filter=models.Filter(must=[_collection_filter()]),
        limit=limit,
        with_payload=True,
    )

    return [
        {
            "chunk_id": str(point.id),
            "doc_id": point.payload["doc_id"],
            "source_filename": point.payload["source_filename"],
            "text": point.payload["text"],
        }
        for point in results.points
    ]


def get_content(chunk_id: str) -> str | None:
    points = _qdrant_client.retrieve(
        collection_name=QDRANT_COLLECTION, ids=[chunk_id], with_payload=True
    )
    if not points:
        return None
    point = points[0]
    if point.payload.get("collection_id") != settings.COLLECTION_ID:
        # Exists, but in a different collection -- treat exactly like not found.
        return None
    return point.payload["text"]


def get_document(doc_id: str) -> str | None:
    points, _ = _qdrant_client.scroll(
        collection_name=QDRANT_COLLECTION,
        scroll_filter=models.Filter(
            must=[
                _collection_filter(),
                models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id)),
            ]
        ),
        with_payload=True,
        limit=1000,
    )
    if not points:
        return None
    points.sort(key=lambda p: p.payload["chunk_index"])
    return "\n\n".join(p.payload["text"] for p in points)


def list_documents() -> list[dict]:
    with _engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, source_filename, status FROM documents "
                "WHERE collection_id = :collection_id ORDER BY created_at DESC"
            ),
            {"collection_id": settings.COLLECTION_ID},
        ).mappings().all()
    return [{"id": str(row["id"]), "source_filename": row["source_filename"], "status": row["status"]} for row in rows]
