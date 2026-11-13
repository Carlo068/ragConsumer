import uuid

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.models import ROLE_RANK, CollectionMember, CollectionRole, User

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


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "not_authenticated", "Not authenticated")

    user = db.get(User, uuid.UUID(user_id))
    if user is None:
        request.session.clear()
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "not_authenticated", "Not authenticated")

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