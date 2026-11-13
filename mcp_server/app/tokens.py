"""Personal access token lookup. Kept free of MCP imports so the rule
"which user does this bearer token belong to" is a small, testable unit."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class TokenOwner:
    user_id: str
    token_id: str


def hash_token(token: str) -> str:
    # Must match backend/app/routers/tokens.py: only this hash is ever stored.
    return hashlib.sha256(token.encode()).hexdigest()


def find_token_owner(engine: Engine, token: str, now: datetime | None = None) -> TokenOwner | None:
    """The user a valid token belongs to, or None.

    Valid means: known, not revoked, not expired. Every failure looks the same
    to the caller, so a probe can't tell "revoked" from "never existed". Stamps
    last_used_at so people can see which tokens are still in use.
    """
    if not token:
        return None
    # Naive UTC, matching the timestamp-without-time-zone columns.
    now = now or datetime.now(UTC).replace(tzinfo=None)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT id, user_id FROM api_tokens "
                "WHERE token_hash = :h AND revoked_at IS NULL AND expires_at > :now"
            ),
            {"h": hash_token(token), "now": now},
        ).first()
        if row is None:
            return None
        conn.execute(
            text("UPDATE api_tokens SET last_used_at = :now WHERE id = :id"),
            {"now": now, "id": row[0]},
        )
    return TokenOwner(user_id=str(row[1]), token_id=str(row[0]))
