from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    QDRANT_URL: str = "http://127.0.0.1:6333"
    # Also the secret Qdrant verifies its JWTs with (service.jwt_rbac), so
    # it is what lets this server mint read-only tokens. Empty = no auth.
    QDRANT_API_KEY: str = ""
    QDRANT_TOKEN_TTL_SECONDS: int = 60

    # Must be exactly the worker's values (see ingestion_worker/app/config.py).
    DENSE_MODEL: str = "jinaai/jina-embeddings-v2-base-es"
    BM25_LANGUAGE: str = "spanish"

    # Where AI clients reach this server; set to the public URL in production.
    PUBLIC_URL: str = "http://localhost:8002"

    HOST: str = "0.0.0.0"
    PORT: int = 8002


settings = Settings()
