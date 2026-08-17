from qdrant_client import QdrantClient, models

from app.config import settings

# Must match ingestion_worker/app/pipeline.py and mcp_server/app/search.py --
# same collection name, since this deletes what those write/read.
QDRANT_COLLECTION = "chunks"

qdrant_client = QdrantClient(url=settings.QDRANT_URL)


def delete_document_chunks(doc_id: str) -> None:
    if not qdrant_client.collection_exists(QDRANT_COLLECTION):
        return
    qdrant_client.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))]
            )
        ),
    )
