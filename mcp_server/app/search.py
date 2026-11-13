from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient, models
from sqlalchemy import bindparam, create_engine, text

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

NO_MATTERS_MESSAGE = (
    "None of your matters is turned on for your AI. "
    "Turn one on from the Collections page of the web app."
)


def get_allowed_matters(user_id: str) -> dict[str, str]:
    """The matters this person's AI may search right now: {matter id: name}.

    Read fresh on every call, never cached or taken from a tool argument. A
    matter counts only if the person both chose it for their AI *and* is still
    a member of it. The second condition is the security one: removing someone
    from a matter cuts their AI off on its very next call, whatever they had
    selected before.
    """
    with _engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT c.id, c.name FROM ai_matter_selections s "
                "JOIN collection_members m "
                "  ON m.collection_id = s.collection_id AND m.user_id = s.user_id "
                "JOIN collections c ON c.id = s.collection_id "
                "WHERE s.user_id = :user_id ORDER BY c.name"
            ),
            {"user_id": user_id},
        ).all()
    return {str(row[0]): row[1] for row in rows}


def _in_matters(matter_ids: list[str]) -> models.FieldCondition:
    return models.FieldCondition(key="collection_id", match=models.MatchAny(any=matter_ids))


def search(user_id: str, query: str, limit: int = 5) -> list[dict]:
    matters = get_allowed_matters(user_id)
    if not matters:
        return [{"message": NO_MATTERS_MESSAGE}]

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
        query_filter=models.Filter(must=[_in_matters(list(matters))]),
        limit=limit,
        with_payload=True,
    )

    return [
        {
            "chunk_id": str(point.id),
            "doc_id": point.payload["doc_id"],
            "matter": matters.get(point.payload["collection_id"], ""),
            "source_filename": point.payload["source_filename"],
            "text": point.payload["text"],
        }
        for point in results.points
    ]


def get_content(user_id: str, chunk_id: str) -> str | None:
    matters = get_allowed_matters(user_id)
    if not matters:
        return NO_MATTERS_MESSAGE

    points = _qdrant_client.retrieve(
        collection_name=QDRANT_COLLECTION, ids=[chunk_id], with_payload=True
    )
    if not points:
        return None
    point = points[0]
    if point.payload.get("collection_id") not in matters:
        # Exists, but in a matter this person's AI can't reach -- treat exactly
        # like not found.
        return None
    return point.payload["text"]


def get_document(user_id: str, doc_id: str) -> str | None:
    matters = get_allowed_matters(user_id)
    if not matters:
        return NO_MATTERS_MESSAGE

    points, _ = _qdrant_client.scroll(
        collection_name=QDRANT_COLLECTION,
        scroll_filter=models.Filter(
            must=[
                _in_matters(list(matters)),
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


def list_documents(user_id: str) -> list[dict]:
    matters = get_allowed_matters(user_id)
    if not matters:
        return [{"message": NO_MATTERS_MESSAGE}]

    with _engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, collection_id, source_filename, status FROM documents "
                "WHERE collection_id IN :ids ORDER BY created_at DESC"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": list(matters)},
        ).mappings().all()
    return [
        {
            "id": str(row["id"]),
            "matter": matters[str(row["collection_id"])],
            "source_filename": row["source_filename"],
            "status": row["status"],
        }
        for row in rows
    ]
