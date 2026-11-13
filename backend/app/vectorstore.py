from qdrant_client import QdrantClient, models

from app.config import settings

qdrant_client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)


def matter_collection_name(collection_id: str) -> str:
    # Must match ingestion_worker/app/pipeline.py and mcp_server/app/search.py.
    # Every matter lives in its own Qdrant collection, so isolation between
    # matters is enforced by Qdrant itself (its access tokens are scoped per
    # collection) instead of by a payload filter that one bug could omit.
    return f"matter_{collection_id}"


def delete_document_chunks(collection_id: str, doc_id: str) -> None:
    name = matter_collection_name(collection_id)
    if not qdrant_client.collection_exists(name):
        return
    qdrant_client.delete(
        collection_name=name,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))]
            )
        ),
    )


def delete_matter_vectors(collection_id: str) -> None:
    """Deleting a matter drops its whole Qdrant collection."""
    name = matter_collection_name(collection_id)
    if qdrant_client.collection_exists(name):
        qdrant_client.delete_collection(name)
