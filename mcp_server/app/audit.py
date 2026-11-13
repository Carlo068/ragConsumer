"""Audit trail for everything an AI assistant reads.

Writes straight into the backend's audit_log table (insert-only; a database
trigger rejects changes and deletions). Fails closed: if an entry can't be
written the exception propagates and the tool call returns nothing, so there is
never a read the firm can't account for.
"""

import json
import uuid

from sqlalchemy import text
from sqlalchemy.engine import Engine

# Must match backend/app/audit.py.
MCP_SEARCH = "mcp_search"
MCP_GET_CONTENT = "mcp_get_content"
MCP_GET_DOCUMENT = "mcp_get_document"
MCP_LIST_DOCUMENTS = "mcp_list_documents"


def record(
    engine: Engine,
    user_id: str,
    action: str,
    *,
    matter_id: str | None = None,
    matter_name: str | None = None,
    target: str | None = None,
    detail: dict | None = None,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO audit_log (id, actor_user_id, actor_email, action, collection_id, "
                "collection_name, target, detail) VALUES (:id, :uid, "
                "(SELECT email FROM users WHERE id = :uid), :action, :cid, :cname, :target, "
                "CAST(:detail AS jsonb))"
            ),
            {
                "id": str(uuid.uuid4()),
                "uid": user_id,
                "action": action,
                "cid": matter_id,
                "cname": matter_name,
                "target": target,
                "detail": json.dumps(detail) if detail is not None else None,
            },
        )
