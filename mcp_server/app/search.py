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

NO_ACTIVE_COLLECTION_MESSAGE = (
    "No collection is currently active. Select one from the frontend's Connect page."
)


def get_active_collection_id() -> str | None:
    # Read fresh on every call (not cached) -- this is what lets toggling the
    # active collection in the frontend take effect immediately, with no
    # mcp_server restart. Still never accepted as a tool argument: the only
    # thing that can change what this server exposes is this row, set via the
    # authenticated web app (require_collection_membership-gated), never by
    # anything an MCP client sends.
    with _engine.connect() as conn:
        row = conn.execute(
            text("SELECT collection_id FROM mcp_active_collection WHERE id = 1")
        ).first()
    return str(row[0]) if row and row[0] is not None else None


def _collection_filter(collection_id: str) -> models.FieldCondition:
    return models.FieldCondition(
        key="collection_id", match=models.MatchValue(value=collection_id)
    )


def search(query: str, limit: int = 5) -> list[dict]:
    collection_id = get_active_collection_id()
    if collection_id is None:
        return [{"message": NO_ACTIVE_COLLECTION_MESSAGE}]

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
        query_filter=models.Filter(must=[_collection_filter(collection_id)]),
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
    collection_id = get_active_collection_id()
    if collection_id is None:
        return NO_ACTIVE_COLLECTION_MESSAGE

    points = _qdrant_client.retrieve(
        collection_name=QDRANT_COLLECTION, ids=[chunk_id], with_payload=True
    )
    if not points:
        return None
    point = points[0]
    if point.payload.get("collection_id") != collection_id:
        # Exists, but in a different collection -- treat exactly like not found.
        return None
    return point.payload["text"]


def get_document(doc_id: str) -> str | None:
    collection_id = get_active_collection_id()
    if collection_id is None:
        return NO_ACTIVE_COLLECTION_MESSAGE

    points, _ = _qdrant_client.scroll(
        collection_name=QDRANT_COLLECTION,
        scroll_filter=models.Filter(
            must=[
                _collection_filter(collection_id),
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
    collection_id = get_active_collection_id()
    if collection_id is None:
        return [{"message": NO_ACTIVE_COLLECTION_MESSAGE}]

    with _engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, source_filename, status FROM documents "
                "WHERE collection_id = :collection_id ORDER BY created_at DESC"
            ),
            {"collection_id": collection_id},
        ).mappings().all()
    return [{"id": str(row["id"]), "source_filename": row["source_filename"], "status": row["status"]} for row in rows]
