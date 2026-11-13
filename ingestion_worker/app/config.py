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


settings = Settings()
