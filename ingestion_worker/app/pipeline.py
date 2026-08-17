import os
import re
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

# --- Object key parsing ---------------------------------------------------
# Keys are written by the backend as: collection-{collection_id}/doc-{doc_id}/{filename}
_KEY_PATTERN = re.compile(r"^collection-(?P<collection_id>[^/]+)/doc-(?P<doc_id>[^/]+)/(?P<filename>.+)$")


def parse_object_key(key: str) -> tuple[str, str, str]:
    match = _KEY_PATTERN.match(key)
    if not match:
        raise ValueError(f"Unexpected object key format: {key!r}")
    return match.group("collection_id"), match.group("doc_id"), match.group("filename")


# --- Postgres status updates ----------------------------------------------
_engine = create_engine(settings.DATABASE_URL)


def update_document_status(doc_id: str, status_value: str) -> None:
    with _engine.begin() as conn:
        conn.execute(
            text("UPDATE documents SET status = :status, updated_at = now() WHERE id = :doc_id"),
            {"status": status_value, "doc_id": doc_id},
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
QDRANT_COLLECTION = "chunks"
DENSE_MODEL_NAME = "BAAI/bge-small-en-v1.5"
DENSE_VECTOR_SIZE = 384
SPARSE_MODEL_NAME = "Qdrant/bm25"

_qdrant_client = QdrantClient(url=settings.QDRANT_URL)
_dense_model = TextEmbedding(model_name=DENSE_MODEL_NAME)
_sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)


def ensure_qdrant_collection() -> None:
    if not _qdrant_client.collection_exists(QDRANT_COLLECTION):
        _qdrant_client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config={
                "dense": models.VectorParams(size=DENSE_VECTOR_SIZE, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={"sparse": models.SparseVectorParams()},
        )


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
        _qdrant_client.upsert(collection_name=QDRANT_COLLECTION, points=points)


# --- End-to-end per-object pipeline -------------------------------------------
def process_object(bucket: str, key: str) -> None:
    collection_id, doc_id, filename = parse_object_key(key)
    update_document_status(doc_id, "processing")

    local_path = None
    try:
        local_path = download_to_temp(bucket, key, filename)
        markdown_text = convert_to_markdown(local_path)
        chunks = chunk_markdown(markdown_text)
        upsert_chunks(collection_id, doc_id, filename, chunks)
        update_document_status(doc_id, "ready")
    except Exception:
        update_document_status(doc_id, "failed")
        raise
    finally:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)
