from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    SESSION_SECRET: str

    MINIO_ENDPOINT: str = "127.0.0.1:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "documents"

    QDRANT_URL: str = "http://127.0.0.1:6333"

    MAX_UPLOAD_SIZE_BYTES: int = 2 * 1024 * 1024

    # Invite links point here; set to the public URL in production.
    FRONTEND_URL: str = "http://localhost:5173"
    INVITE_TTL_HOURS: int = 72
    MIN_PASSWORD_LENGTH: int = 12


settings = Settings()
