from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient, models
from sqlalchemy import bindparam, create_engine, text

from app import audit
from app.config import settings
from app.qdrant_access import scoped_client

# Must match ingestion_worker/app/pipeline.py exactly -- same collection naming,
# same vector names, same embedding models -- since this reads what that writes.
DENSE_MODEL_NAME = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL_NAME = "Qdrant/bm25"

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


def matter_collection_name(matter_id: str) -> str:
    # One Qdrant collection per matter. A tool call only ever names collections
    # of matters the person's AI is allowed to reach (see get_allowed_matters),
    # so a different matter's data is simply never queried.
    return f"matter_{matter_id}"


def _open_matters(matters: dict[str, str]) -> tuple[QdrantClient, dict[str, str]]:
    """A Qdrant client able to read only these matters' collections, plus
    {qdrant collection name: matter name} for those that exist yet (a matter's
    collection is created on its first ingest).

    The client carries a short-lived read-only token naming exactly these
    collections, so Qdrant itself refuses anything else.
    """
    names = {matter_collection_name(matter_id): name for matter_id, name in matters.items()}
    client = scoped_client(
        settings.QDRANT_URL, settings.QDRANT_API_KEY, list(names), settings.QDRANT_TOKEN_TTL_SECONDS
    )
    return client, {n: m for n, m in names.items() if client.collection_exists(n)}


def _matter_id(collection_name: str) -> str:
    return collection_name.removeprefix("matter_")


def search(user_id: str, query: str, limit: int = 5) -> list[dict]:
    matters = get_allowed_matters(user_id)
    if not matters:
        audit.record(
            _engine, user_id, audit.MCP_SEARCH, detail={"query": query, "matters_searched": 0}
        )
        return [{"message": NO_MATTERS_MESSAGE}]

    dense_vec = list(_dense_model.embed([query]))[0]
    sparse_vec = list(_sparse_model.embed([query]))[0]

    client, collections = _open_matters(matters)
    hits = []
    for collection_name, matter_name in collections.items():
        results = client.query_points(
            collection_name=collection_name,
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
            limit=limit,
            with_payload=True,
        )
        hits.extend((point, collection_name, matter_name) for point in results.points)

    # Each matter was ranked on its own; interleave by fused score and keep the
    # best few overall.
    hits.sort(key=lambda hit: hit[0].score, reverse=True)
    top = hits[:limit]

    # One entry per matter searched, so "who searched matter X" is complete even
    # when nothing came back. Written before anything is returned.
    for matter_id, matter_name in matters.items():
        returned = [str(p.id) for p, cname, _ in top if _matter_id(cname) == matter_id]
        audit.record(
            _engine, user_id, audit.MCP_SEARCH, matter_id=matter_id, matter_name=matter_name,
            detail={"query": query, "chunk_ids": returned},
        )

    return [
        {
            "chunk_id": str(point.id),
            "doc_id": point.payload["doc_id"],
            "matter": matter_name,
            "source_filename": point.payload["source_filename"],
            "text": point.payload["text"],
        }
        for point, _, matter_name in top
    ]


def get_content(user_id: str, chunk_id: str) -> str | None:
    matters = get_allowed_matters(user_id)
    if not matters:
        audit.record(_engine, user_id, audit.MCP_GET_CONTENT, target=chunk_id,
                     detail={"matters_searched": 0})
        return NO_MATTERS_MESSAGE

    # The chunk's matter isn't known up front, so look in each matter this
    # person's AI can reach. A chunk elsewhere is never looked at, and so is
    # indistinguishable from one that doesn't exist.
    client, collections = _open_matters(matters)
    for collection_name, matter_name in collections.items():
        points = client.retrieve(
            collection_name=collection_name, ids=[chunk_id], with_payload=True
        )
        if points:
            audit.record(
                _engine, user_id, audit.MCP_GET_CONTENT, matter_id=_matter_id(collection_name),
                matter_name=matter_name, target=chunk_id,
            )
            return points[0].payload["text"]
    audit.record(_engine, user_id, audit.MCP_GET_CONTENT, target=chunk_id, detail={"found": False})
    return None


def get_document(user_id: str, doc_id: str) -> str | None:
    matters = get_allowed_matters(user_id)
    if not matters:
        audit.record(_engine, user_id, audit.MCP_GET_DOCUMENT, target=doc_id,
                     detail={"matters_searched": 0})
        return NO_MATTERS_MESSAGE

    client, collections = _open_matters(matters)
    for collection_name, matter_name in collections.items():
        points, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))]
            ),
            with_payload=True,
            limit=1000,
        )
        if points:
            audit.record(
                _engine, user_id, audit.MCP_GET_DOCUMENT, matter_id=_matter_id(collection_name),
                matter_name=matter_name, target=doc_id, detail={"chunks": len(points)},
            )
            points.sort(key=lambda p: p.payload["chunk_index"])
            return "\n\n".join(p.payload["text"] for p in points)
    audit.record(_engine, user_id, audit.MCP_GET_DOCUMENT, target=doc_id, detail={"found": False})
    return None


def list_documents(user_id: str) -> list[dict]:
    matters = get_allowed_matters(user_id)
    if not matters:
        audit.record(_engine, user_id, audit.MCP_LIST_DOCUMENTS, detail={"matters_searched": 0})
        return [{"message": NO_MATTERS_MESSAGE}]

    with _engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, collection_id, source_filename, status FROM documents "
                "WHERE collection_id IN :ids ORDER BY created_at DESC"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": list(matters)},
        ).mappings().all()

    for matter_id, matter_name in matters.items():
        count = sum(1 for row in rows if str(row["collection_id"]) == matter_id)
        audit.record(
            _engine, user_id, audit.MCP_LIST_DOCUMENTS, matter_id=matter_id,
            matter_name=matter_name, detail={"documents": count},
        )

    return [
        {
            "id": str(row["id"]),
            "matter": matters[str(row["collection_id"])],
            "source_filename": row["source_filename"],
            "status": row["status"],
        }
        for row in rows
    ]
