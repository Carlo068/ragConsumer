import uuid
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.errors import ApiError
from app.models import ROLE_RANK, CollectionMember, CollectionRole, User, UserSession

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


# A real hash to verify against when the email is unknown, so a login for a
# missing account costs the same time as one for an existing account and the
# response time doesn't reveal which emails have accounts.
DUMMY_PASSWORD_HASH = _hasher.hash("not-a-real-password")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def utcnow() -> datetime:
    # Naive UTC, to match the timestamp-without-time-zone columns.
    return datetime.now(UTC).replace(tzinfo=None)


# last_seen_at is refreshed at most this often, so a busy page does not write
# to the database on every request.
_SEEN_REFRESH = timedelta(seconds=60)


def start_session(db: Session, request: Request, user: User) -> UserSession:
    """Signs `user` in: a new server-side session, and a cookie that carries only its id."""
    request.session.clear()
    now = utcnow()
    row = UserSession(
        user_id=user.id,
        created_at=now,
        last_seen_at=now,
        ip=request.client.host if request.client else None,
        user_agent=(request.headers.get("user-agent") or "")[:255] or None,
    )
    db.add(row)
    db.flush()
    request.session["sid"] = str(row.id)
    return row


def end_session(db: Session, request: Request) -> None:
    sid = request.session.get("sid")
    if sid:
        try:
            db.execute(
                update(UserSession)
                .where(UserSession.id == uuid.UUID(sid), UserSession.ended_at.is_(None))
                .values(ended_at=utcnow())
            )
        except ValueError:
            pass
    request.session.clear()


def end_user_sessions(db: Session, user_id: uuid.UUID, *, except_session: uuid.UUID | None = None) -> int:
    """Ends every open session of a person (all their browsers). Returns how many."""
    query = update(UserSession).where(UserSession.user_id == user_id, UserSession.ended_at.is_(None))
    if except_session is not None:
        query = query.where(UserSession.id != except_session)
    return db.execute(query.values(ended_at=utcnow())).rowcount or 0


def _reject(request: Request) -> ApiError:
    request.session.clear()
    return ApiError(status.HTTP_401_UNAUTHORIZED, "not_authenticated", "Not authenticated")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """The signed-in person, or 401. The cookie is only a pointer to a server-side
    session, so ending that session, disabling the account or a long idle time
    all take effect on the very next request."""
    sid = request.session.get("sid")
    if not sid:
        raise _reject(request)
    try:
        session_id = uuid.UUID(sid)
    except ValueError:
        raise _reject(request)

    row = db.get(UserSession, session_id)
    now = utcnow()
    if row is None:
        raise _reject(request)
    if row.ended_at is not None:
        raise _reject(request)
    if now - row.last_seen_at > timedelta(minutes=settings.SESSION_IDLE_MINUTES):
        row.ended_at = now
        db.commit()
        raise _reject(request)

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        row.ended_at = now
        db.commit()
        raise _reject(request)

    if now - row.last_seen_at > _SEEN_REFRESH:
        row.last_seen_at = now
        db.commit()
    request.state.session_id = row.id
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    # 403 is fine here, unlike the 404 used for matters: the admin pages'
    # existence isn't sensitive, only what's inside matters is.
    if not current_user.is_admin:
        raise ApiError(status.HTTP_403_FORBIDDEN, "admin_required", "Administrator access required")
    return current_user


def require_collection_role(
    db: Session,
    user_id: uuid.UUID,
    collection_id: uuid.UUID,
    minimum: CollectionRole = CollectionRole.viewer,
) -> CollectionMember:
    """The one gate every matter route goes through.

    Not a member -> 404, so the response never reveals that the matter exists.
    A member whose role is too low -> 403: they already know it exists, and
    telling them what they lack is more useful than a misleading 404.
    """
    member = db.scalar(
        select(CollectionMember).where(
            CollectionMember.user_id == user_id,
            CollectionMember.collection_id == collection_id,
        )
    )
    if member is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "matter_not_found", "Collection not found")
    if ROLE_RANK[member.role] < ROLE_RANK[minimum]:
        raise ApiError(
            status.HTTP_403_FORBIDDEN,
            "role_required",
            f"This action requires the {minimum.value} role or higher on this collection",
            role=minimum.value,
        )
    return member


def require_collection_membership(
    db: Session, user_id: uuid.UUID, collection_id: uuid.UUID
) -> None:
    """Any role at all. Kept for callers that only need 'is a member'."""
    require_collection_role(db, user_id, collection_id, CollectionRole.viewer)