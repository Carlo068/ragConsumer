from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings

from app import search as search_module
from app.auth import PersonalTokenVerifier, current_user_id
from app.config import settings
from app.search import _engine

# Every request must carry "Authorization: Bearer rag_..." (a personal token
# from the web app). Without a valid one the server answers 401 before any
# tool runs.
mcp = MCPServer(
    "ragconsumer-collection",
    token_verifier=PersonalTokenVerifier(_engine),
    auth=AuthSettings(
        issuer_url=settings.PUBLIC_URL,
        resource_server_url=settings.PUBLIC_URL,
    ),
)


@mcp.tool()
def search(query: str) -> list[dict]:
    """Search this collection's documents for chunks relevant to the query.

    Returns up to 5 matching chunks, each with chunk_id, doc_id, source_filename, and text.
    """
    return search_module.search(current_user_id(), query)


@mcp.tool()
def get_content(chunk_id: str) -> str:
    """Fetch the full text of a specific chunk by its chunk_id (as returned by search)."""
    content = search_module.get_content(current_user_id(), chunk_id)
    if content is None:
        return "No such chunk in this collection."
    return content


@mcp.tool()
def get_document(doc_id: str) -> str:
    """Reassemble and return the full text of a document by its doc_id, from all its chunks in order."""
    content = search_module.get_document(current_user_id(), doc_id)
    if content is None:
        return "No such document in this collection."
    return content


@mcp.tool()
def list_documents() -> list[dict]:
    """List all documents in this collection with their id, filename, and ingestion status."""
    return search_module.list_documents(current_user_id())


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host=settings.HOST, port=settings.PORT)
