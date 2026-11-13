from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    QDRANT_URL: str = "http://127.0.0.1:6333"

    # Where AI clients reach this server; set to the public URL in production.
    PUBLIC_URL: str = "http://localhost:8002"

    HOST: str = "0.0.0.0"
    PORT: int = 8002


settings = Settings()
