"""The one place application code writes to the audit log.

record() adds the entry to the caller's open transaction, so the entry and the
action it describes are saved together or not at all. There is deliberately no
function here to change or remove entries."""

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog, Collection, User

# Action names, kept in one place so the admin view can offer them as filters.
LOGIN = "login"
LOGIN_FAILED = "login_failed"
LOGIN_THROTTLED = "login_throttled"
LOGOUT = "logout"
PASSWORD_CHANGED = "password_changed"
PASSWORD_RESET_CREATED = "password_reset_created"
PASSWORD_RESET_COMPLETED = "password_reset_completed"
USER_DISABLED = "user_disabled"
USER_ENABLED = "user_enabled"
SESSIONS_ENDED = "sessions_ended"
INVITE_CREATED = "invite_created"
INVITE_REVOKED = "invite_revoked"
INVITE_ACCEPTED = "invite_accepted"
MATTER_CREATED = "matter_created"
MATTER_RENAMED = "matter_renamed"
MATTER_DELETED = "matter_deleted"
MEMBER_ADDED = "member_added"
MEMBER_ROLE_CHANGED = "member_role_changed"
MEMBER_REMOVED = "member_removed"
DOCUMENT_UPLOADED = "document_uploaded"
DOCUMENT_DELETED = "document_deleted"
DOCUMENT_REINGESTED = "document_reingested"
TOKEN_CREATED = "token_created"
TOKEN_REVOKED = "token_revoked"
AI_ACCESS_ENABLED = "ai_access_enabled"
AI_ACCESS_DISABLED = "ai_access_disabled"
# Written by mcp_server, not by this app (see mcp_server/app/audit.py).
MCP_SEARCH = "mcp_search"
MCP_GET_CONTENT = "mcp_get_content"
MCP_GET_DOCUMENT = "mcp_get_document"
MCP_LIST_DOCUMENTS = "mcp_list_documents"
ACCESS_DENIED = "access_denied"
AUDIT_VIEWED = "audit_viewed"
AUDIT_EXPORTED = "audit_exported"

ALL_ACTIONS = [
    LOGIN, LOGIN_FAILED, LOGIN_THROTTLED, LOGOUT, PASSWORD_CHANGED, PASSWORD_RESET_CREATED,
    PASSWORD_RESET_COMPLETED, USER_DISABLED, USER_ENABLED, SESSIONS_ENDED, INVITE_CREATED, INVITE_REVOKED, INVITE_ACCEPTED,
    MATTER_CREATED, MATTER_RENAMED, MATTER_DELETED,
    MEMBER_ADDED, MEMBER_ROLE_CHANGED, MEMBER_REMOVED,
    DOCUMENT_UPLOADED, DOCUMENT_DELETED, DOCUMENT_REINGESTED, TOKEN_CREATED, TOKEN_REVOKED,
    AI_ACCESS_ENABLED, AI_ACCESS_DISABLED,
    MCP_SEARCH, MCP_GET_CONTENT, MCP_GET_DOCUMENT, MCP_LIST_DOCUMENTS,
    ACCESS_DENIED, AUDIT_VIEWED, AUDIT_EXPORTED,
]


def record(
    db: Session,
    action: str,
    *,
    actor: User | None = None,
    collection_id: uuid.UUID | None = None,
    collection_name: str | None = None,
    target: str | None = None,
    detail: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    if collection_id is not None and collection_name is None:
        collection = db.get(Collection, collection_id)
        collection_name = collection.name if collection else None
    db.add(
        AuditLog(
            actor_user_id=actor.id if actor else None,
            actor_email=actor.email if actor else None,
            action=action,
            collection_id=collection_id,
            collection_name=collection_name,
            target=target,
            detail=detail,
            ip=request.client.host if request and request.client else None,
        )
    )
