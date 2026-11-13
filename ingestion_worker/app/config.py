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
    # A document still "processing" after this long is marked failed (retryable).
    STUCK_AFTER_MINUTES: float = 60.0

    # Text recognition for scanned PDFs. A PDF with fewer than this many
    # characters of text per page is treated as a scan and run through OCR.
    OCR_LANGUAGES: str = "spa+eng"
    OCR_MIN_CHARS_PER_PAGE: int = 50
    OCR_TIMEOUT_SECONDS: int = 1800


settings = Settings()
