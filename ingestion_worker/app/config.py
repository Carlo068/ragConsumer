from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str

    MINIO_ENDPOINT: str = "127.0.0.1:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "documents"

    QDRANT_URL: str = "http://127.0.0.1:6333"
    # Empty = no auth (plain local Qdrant). Always set in compose.
    QDRANT_API_KEY: str = ""

    # How often the worker looks for pending documents even without a webhook.
    QUEUE_POLL_SECONDS: float = 10.0
    # A document with no progress (no batch indexed) for this long is marked
    # failed (retryable). Indexing records progress after every batch, so a
    # large file that is still moving is never cut off.
    STUCK_AFTER_MINUTES: float = 60.0

    # Search models. Chosen on the Spanish legal evaluation set (eval/, KAN-79).
    # The MCP server must use exactly the same two values, and changing them
    # means re-indexing every document (backend/scripts/reindex_all.py).
    DENSE_MODEL: str = "jinaai/jina-embeddings-v2-base-es"
    BM25_LANGUAGE: str = "spanish"

    # Text recognition for scanned PDFs. A PDF with fewer than this many
    # characters of text per page is treated as a scan and run through OCR.
    OCR_LANGUAGES: str = "spa+eng"
    OCR_MIN_CHARS_PER_PAGE: int = 50
    OCR_TIMEOUT_SECONDS: int = 1800


settings = Settings()
