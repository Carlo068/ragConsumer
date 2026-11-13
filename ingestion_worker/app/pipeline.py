import os
import tempfile
import uuid

from fastembed import SparseTextEmbedding, TextEmbedding
from markitdown import MarkItDown
from minio import Minio
from qdrant_client import QdrantClient, models
from sqlalchemy import create_engine, text

from app.config import settings
from app import formats
from app.chunking import chunk_markdown
from app.failures import DocumentDeleted, IndexOutdated, NoTextFound, failure_reason
from app.index_model import fingerprint, is_compatible
from app.ocr import count_pdf_pages, needs_ocr, run_ocr

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


def _markitdown(path: str) -> str:
    return _converter.convert(path).text_content


def convert_to_markdown(path: str) -> str:
    """Convert a file to markdown. Formats MarkItDown does not handle (legacy
    .doc, and email) have their own converters."""
    extension = os.path.splitext(path)[1].lower()
    if extension == ".eml":
        return formats.eml_to_text(path, _markitdown)
    if extension == ".msg":
        return formats.msg_to_text(path, _markitdown)
    if extension == ".doc":
        return formats.doc_to_text(path)
    return _markitdown(path)


def convert_with_ocr(path: str) -> str:
    """Convert a file to markdown, running OCR first when it is a scanned PDF."""
    markdown_text = convert_to_markdown(path)
    if path.lower().endswith(".pdf") and needs_ocr(
        markdown_text, count_pdf_pages(path), settings.OCR_MIN_CHARS_PER_PAGE
    ):
        ocr_path = path + ".ocr.pdf"
        try:
            run_ocr(path, ocr_path, settings.OCR_LANGUAGES, settings.OCR_TIMEOUT_SECONDS)
            markdown_text = convert_to_markdown(ocr_path)
        finally:
            if os.path.exists(ocr_path):
                os.remove(ocr_path)
    return markdown_text



# --- Embedding + Qdrant upsert -----------------------------------------------
SPARSE_MODEL_NAME = "Qdrant/bm25"

_qdrant_client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)
_dense_model = TextEmbedding(model_name=settings.DENSE_MODEL)
_sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME, language=settings.BM25_LANGUAGE)
DENSE_VECTOR_SIZE = _dense_model.embedding_size
INDEX_FINGERPRINT = fingerprint(settings.DENSE_MODEL, settings.BM25_LANGUAGE)


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
            # BM25 needs Qdrant's IDF modifier to weigh rare terms properly.
            sparse_vectors_config={"sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)},
            metadata={"embedding": INDEX_FINGERPRINT},
        )
    elif not is_compatible(_qdrant_client.get_collection(name).config.metadata, INDEX_FINGERPRINT):
        raise IndexOutdated(name)
    return name


def chunk_point_id(doc_id: str, chunk_index: int) -> str:
    # Deterministic from (doc_id, chunk_index) so a redelivered webhook upserts
    # the same points instead of duplicating them.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{chunk_index}"))


EMBED_BATCH_SIZE = 64


def touch_document(doc_id: str) -> bool:
    """Heartbeat after each batch: records that this document is still making
    progress (so a long file is not mistaken for a stuck one) and reports
    whether it still exists (so a deleted file stops being indexed at once)."""
    with _engine.begin() as conn:
        result = conn.execute(
            text("UPDATE documents SET updated_at = now() WHERE id = :doc_id"), {"doc_id": doc_id}
        )
    return result.rowcount > 0


def upsert_chunks(collection_id: str, doc_id: str, filename: str, chunks: list[str]) -> None:
    # Embedding + upserting the whole document's chunks in one shot holds every
    # dense/sparse vector for every chunk in memory at once -- for a large
    # document that's enough to OOM-kill the worker (confirmed: a 5.5MB, ~1300
    # page PDF did exactly this). Batching bounds peak memory to one batch's
    # worth of vectors regardless of document size.
    collection_name = ensure_matter_collection(collection_id)
    for batch_start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[batch_start : batch_start + EMBED_BATCH_SIZE]

        dense_vectors = list(_dense_model.passage_embed(batch))
        sparse_vectors = list(_sparse_model.passage_embed(batch))

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
        if not touch_document(doc_id):
            raise DocumentDeleted(doc_id)


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
        markdown_text = convert_with_ocr(local_path)
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
    except DocumentDeleted:
        # Deleting a file already cleaned up what existed then; remove what this
        # run wrote since, and stop. Not a failure.
        _discard_vectors_of_deleted_document(job.collection_id, job.doc_id)
    except Exception as exc:
        # The person sees a plain-language reason; the details stay in our log.
        update_document_status(job.doc_id, "failed", failure_reason(exc))
        raise
    finally:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)
