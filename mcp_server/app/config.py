from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # The single collection this server instance is bound to. Never accepted
    # as a tool argument -- that's the whole point of the network-scoped
    # design: nothing in the conversation can ever change what this server
    # is allowed to query.
    COLLECTION_ID: str

    DATABASE_URL: str
    QDRANT_URL: str = "http://127.0.0.1:6333"

    HOST: str = "0.0.0.0"
    PORT: int = 8002


settings = Settings()
