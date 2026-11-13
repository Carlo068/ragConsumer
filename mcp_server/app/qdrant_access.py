"""Short-lived, read-only Qdrant access limited to specific matters.

Qdrant (service.jwt_rbac) accepts a JWT signed with its API key whose `access`
claim lists exactly which collections it may read. Every tool call mints one
for the person's allowed matters only, so even a bug in this server's own
query code cannot make Qdrant return another matter's chunks: Qdrant refuses.
Kept free of MCP and search imports so it can be tested on its own.
"""

import time

import jwt
from qdrant_client import QdrantClient


def mint_read_token(
    collection_names: list[str], secret: str, ttl_seconds: int, now: float | None = None
) -> str:
    issued = time.time() if now is None else now
    return jwt.encode(
        {
            "exp": int(issued) + ttl_seconds,
            "access": [{"collection": name, "access": "r"} for name in collection_names],
        },
        secret,
        algorithm="HS256",
    )


def scoped_client(
    url: str, secret: str, collection_names: list[str], ttl_seconds: int = 60
) -> QdrantClient:
    if not secret:
        # Plain local Qdrant without auth (tests, quick experiments).
        return QdrantClient(url=url)
    return QdrantClient(
        url=url, api_key=mint_read_token(collection_names, secret, ttl_seconds)
    )
