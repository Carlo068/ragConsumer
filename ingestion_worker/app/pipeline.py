import os
import tempfile
import uuid

from fastembed import SparseTextEmbedding, TextEmbedding
from langchain_core.documents import Document as LcDocument
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from markitdown import MarkItDown
from minio import Minio
from qdrant_client import QdrantClient, models
from sqlalchemy import create_engine, text

from app.config import settings
from app.failures import NoTextFound, failure_reason

# --- Postgres status updates ----------------------------------------------
_engine = create_engine(settings.DATABASE_URL)


def update_document_status(doc_id: str, status_value: str, error: str | None = None) -> None:
    with _engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE documents SET status = :status, error_message = :error, "
                "updated_at = now() WHERE id = :doc_id"
            ),
            {"status": status_value, "error": error, "doc_id": doc_id},
        )


# --- MinIO download ---------------------------------------------------------
_minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)


def download_to_temp(bucket: str, key: str, filename: str) -> str:
    suffix = os.path.splitext(filename)[1]
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    _minio_client.fget_object(bucket, key, path)
    return path


# --- Conversion + chunking ---------------------------------------------------
_converter = MarkItDown()
_header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
    strip_headers=False,
)
_recursive_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)


def convert_to_markdown(path: str) -> str:
    return _converter.convert(path).text_content


def chunk_markdown(markdown_text: str) -> list[str]:
    header_docs = _header_splitter.split_text(markdown_text)
    if not header_docs:
        header_docs = [LcDocument(page_content=markdown_text)]
    final_docs = _recursive_splitter.split_documents(header_docs)
    return [d.page_content for d in final_docs if d.page_content.strip()]


# --- Embedding + Qdrant upsert -----------------------------------------------
DENSE_MODEL_NAME = "BAAI/bge-small-en-v1.5"
DENSE_VECTOR_SIZE = 384
SPARSE_MODEL_NAME = "Qdrant/bm25"

_qdrant_client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)
_dense_model = TextEmbedding(model_name=DENSE_MODEL_NAME)
_sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)


def matter_collection_name(collection_id: str) -> str:
    # Must match backend/app/vectorstore.py and mcp_server/app/search.py: one
    # Qdrant collection per matter, so Qdrant itself keeps matters apart.
    return f"matter_{collection_id}"


def ensure_matter_collection(collection_id: str) -> str:
    name = matter_collection_name(collection_id)
    if not _qdrant_client.collection_exists(name):
        _qdrant_client.create_collection(
            collection_name=name,
            vectors_config={
                "dense": models.VectorParams(size=DENSE_VECTOR_SIZE, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={"sparse": models.SparseVectorParams()},
        )
    return name


def chunk_point_id(doc_id: str, chunk_index: int) -> str:
    # Deterministic from (doc_id, chunk_index) so a redelivered webhook upserts
    # the same points instead of duplicating them.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{chunk_index}"))


EMBED_BATCH_SIZE = 64


def upsert_chunks(collection_id: str, doc_id: str, filename: str, chunks: list[str]) -> None:
    # Embedding + upserting the whole document's chunks in one shot holds every
    # dense/sparse vector for every chunk in memory at once -- for a large
    # document that's enough to OOM-kill the worker (confirmed: a 5.5MB, ~1300
    # page PDF did exactly this). Batching bounds peak memory to one batch's
    # worth of vectors regardless of document size.
    collection_name = ensure_matter_collection(collection_id)
    for batch_start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[batch_start : batch_start + EMBED_BATCH_SIZE]

        dense_vectors = list(_dense_model.embed(batch))
        sparse_vectors = list(_sparse_model.embed(batch))

        points = [
            models.PointStruct(
                id=chunk_point_id(doc_id, batch_start + offset),
                vector={
                    "dense": dense_vec.tolist(),
                    "sparse": models.SparseVector(
                        indices=sparse_vec.indices.tolist(),
                        values=sparse_vec.values.tolist(),
                    ),
                },
                payload={
                    "collection_id": collection_id,
                    "doc_id": doc_id,
                    "chunk_index": batch_start + offset,
                    "source_filename": filename,
                    "text": text_chunk,
                },
            )
            for offset, (text_chunk, dense_vec, sparse_vec) in enumerate(
                zip(batch, dense_vectors, sparse_vectors)
            )
        ]
        _qdrant_client.upsert(collection_name=collection_name, points=points)


# --- End-to-end per-document pipeline -----------------------------------------
def _document_still_exists(doc_id: str) -> bool:
    with _engine.connect() as conn:
        return conn.execute(
            text("SELECT 1 FROM documents WHERE id = :doc_id"), {"doc_id": doc_id}
        ).first() is not None


def _matter_still_exists(collection_id: str) -> bool:
    with _engine.connect() as conn:
        return conn.execute(
            text("SELECT 1 FROM collections WHERE id = :collection_id"),
            {"collection_id": collection_id},
        ).first() is not None


def _discard_vectors_of_deleted_document(collection_id: str, doc_id: str) -> None:
    """The document (or its whole matter) was deleted while we were indexing it.
    Deleting cleans Qdrant first, so anything written after that would otherwise
    stay searchable with nothing left to delete it."""
    name = matter_collection_name(collection_id)
    if not _matter_still_exists(collection_id):
        if _qdrant_client.collection_exists(name):
            _qdrant_client.delete_collection(name)
        return
    _qdrant_client.delete(
        collection_name=name,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))]
            )
        ),
    )


def process_document(job) -> None:
    """Index one claimed document (the queue has already marked it processing)."""
    local_path = None
    try:
        local_path = download_to_temp(settings.MINIO_BUCKET, job.object_key, job.filename)
        markdown_text = convert_to_markdown(local_path)
        chunks = chunk_markdown(markdown_text)
        if not chunks:
            # Reading "succeeded" but found nothing to search. Saying "ready"
            # would be a lie: the file would silently never match anything.
            raise NoTextFound()
        upsert_chunks(job.collection_id, job.doc_id, job.filename, chunks)
        if _document_still_exists(job.doc_id):
            update_document_status(job.doc_id, "ready")
        else:
            _discard_vectors_of_deleted_document(job.collection_id, job.doc_id)
    except Exception as exc:
        # The person sees a plain-language reason; the details stay in our log.
        update_document_status(job.doc_id, "failed", failure_reason(exc))
        raise
    finally:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)
