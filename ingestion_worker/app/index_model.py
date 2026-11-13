"""Which search models an index was built with.

The worker writes the fingerprint into each matter's Qdrant collection when it
creates it; the worker and the MCP server compare against it so a collection
built with different models (different vector size, different language rules)
is never silently queried or extended. Keep this file identical in the worker
and the MCP server.
"""


def fingerprint(dense_model: str, bm25_language: str) -> str:
    return f"{dense_model}|bm25:{bm25_language}|idf"


def is_compatible(collection_metadata: dict | None, expected: str) -> bool:
    return (collection_metadata or {}).get("embedding") == expected
