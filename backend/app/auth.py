import uuid

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CollectionMember, User

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    user = db.get(User, uuid.UUID(user_id))
    if user is None:
        request.session.clear()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    return user


def require_collection_membership(
    db: Session, user_id: uuid.UUID, collection_id: uuid.UUID
) -> None:
    member = db.scalar(
        select(CollectionMember).where(
            CollectionMember.user_id == user_id,
            CollectionMember.collection_id == collection_id,
        )
    )
    if member is None:
        # 404, not 403 -- don't reveal whether the collection exists at all
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Collection not found")