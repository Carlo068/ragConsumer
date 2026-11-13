from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    SESSION_SECRET: str
    # Behind HTTPS (production) set SESSION_HTTPS_ONLY=true so the cookie is
    # never sent over plain HTTP. Sessions last SESSION_MAX_AGE_HOURS.
    SESSION_HTTPS_ONLY: bool = False
    SESSION_MAX_AGE_HOURS: int = 12

    MINIO_ENDPOINT: str = "127.0.0.1:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "documents"

    QDRANT_URL: str = "http://127.0.0.1:6333"
    # Empty = no auth (plain local Qdrant). Always set in compose.
    QDRANT_API_KEY: str = ""

    MAX_UPLOAD_SIZE_BYTES: int = 2 * 1024 * 1024

    # Invite links point here; set to the public URL in production.
    FRONTEND_URL: str = "http://localhost:5173"
    INVITE_TTL_HOURS: int = 72
    MIN_PASSWORD_LENGTH: int = 12

    # MCP personal access tokens
    TOKEN_TTL_DAYS: int = 90
    MAX_ACTIVE_TOKENS_PER_USER: int = 10


settings = Settings()
