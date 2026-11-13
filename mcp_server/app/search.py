from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient, models
from sqlalchemy import bindparam, create_engine, text

from app import audit
from app.ids import is_valid_id
from app.config import settings
from app.index_model import fingerprint, is_compatible
from app.matters import get_allowed_matters as _get_allowed_matters
from app.matters import matter_collection_name
from app.qdrant_access import scoped_client

# Must match ingestion_worker/app/pipeline.py exactly -- same collection naming,
# same vector names, same embedding models -- since this reads what that writes.
SPARSE_MODEL_NAME = "Qdrant/bm25"

_dense_model = TextEmbedding(model_name=settings.DENSE_MODEL)
_sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME, language=settings.BM25_LANGUAGE)
INDEX_FINGERPRINT = fingerprint(settings.DENSE_MODEL, settings.BM25_LANGUAGE)
_engine = create_engine(settings.DATABASE_URL)

NO_MATTERS_MESSAGE = (
    "None of your matters is turned on for your AI. "
    "Turn one on from the Collections page of the web app."
)


def get_allowed_matters(user_id: str) -> dict[str, str]:
    return _get_allowed_matters(_engine, user_id)


def _open_matters(matters: dict[str, str]) -> tuple[QdrantClient, dict[str, str], list[str]]:
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
    existing = {n: m for n, m in names.items() if client.collection_exists(n)}
    # A collection built with different search models (vector size, language
    # rules) must not be queried with ours: skip it and say so, rather than
    # failing or returning nonsense. It is rebuilt by backend/scripts/reindex_all.py.
    usable, stale = {}, []
    for collection_name, matter_name in existing.items():
        if is_compatible(client.get_collection(collection_name).config.metadata, INDEX_FINGERPRINT):
            usable[collection_name] = matter_name
        else:
            stale.append(matter_name)
    return client, usable, stale


def _matter_id(collection_name: str) -> str:
    return collection_name.removeprefix("matter_")


def search(user_id: str, query: str, limit: int = 5) -> list[dict]:
    matters = get_allowed_matters(user_id)
    if not matters:
        audit.record(
            _engine, user_id, audit.MCP_SEARCH, detail={"query": query, "matters_searched": 0}
        )
        return [{"message": NO_MATTERS_MESSAGE}]

    dense_vec = next(iter(_dense_model.query_embed(query)))
    sparse_vec = next(iter(_sparse_model.query_embed(query)))

    client, collections, stale = _open_matters(matters)
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

    results = [
        {
            "chunk_id": str(point.id),
            "doc_id": point.payload["doc_id"],
            "matter": matter_name,
            "source_filename": point.payload["source_filename"],
            "text": point.payload["text"],
        }
        for point, _, matter_name in top
    ]
    if stale:
        results.append(
            {
                "message": "The search index for "
                + ", ".join(stale)
                + " is being rebuilt, so its documents cannot be searched yet."
            }
        )
    return results


def get_content(user_id: str, chunk_id: str) -> str | None:
    if not is_valid_id(chunk_id):
        # Not something we ever hand out: answer like a missing chunk, and never
        # pass it on to Qdrant, whose error text would go back to the model.
        audit.record(_engine, user_id, audit.MCP_GET_CONTENT, target=str(chunk_id)[:200], detail={"found": False, "malformed": True})
        return None
    matters = get_allowed_matters(user_id)
    if not matters:
        audit.record(_engine, user_id, audit.MCP_GET_CONTENT, target=chunk_id,
                     detail={"matters_searched": 0})
        return NO_MATTERS_MESSAGE

    # The chunk's matter isn't known up front, so look in each matter this
    # person's AI can reach. A chunk elsewhere is never looked at, and so is
    # indistinguishable from one that doesn't exist.
    client, collections, _ = _open_matters(matters)
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
    if not is_valid_id(doc_id):
        audit.record(_engine, user_id, audit.MCP_GET_DOCUMENT, target=str(doc_id)[:200], detail={"found": False, "malformed": True})
        return None
    matters = get_allowed_matters(user_id)
    if not matters:
        audit.record(_engine, user_id, audit.MCP_GET_DOCUMENT, target=doc_id,
                     detail={"matters_searched": 0})
        return NO_MATTERS_MESSAGE

    client, collections, _ = _open_matters(matters)
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
