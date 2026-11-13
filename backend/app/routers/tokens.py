import hashlib
import secrets
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.db import get_db
from app.models import ApiToken, User
from app.routers.admin import utcnow
from app.schemas import TokenCreate, TokenCreated, TokenOut

router = APIRouter(prefix="/tokens", tags=["tokens"])

TOKEN_PREFIX = "rag_"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _active(user_id: uuid.UUID):
    return (ApiToken.user_id == user_id, ApiToken.revoked_at.is_(None), ApiToken.expires_at > utcnow())


@router.get("", response_model=list[TokenOut])
def list_my_tokens(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Only your own, and only live ones: revoked and expired tokens are noise.
    return db.scalars(
        select(ApiToken).where(*_active(current_user.id)).order_by(ApiToken.created_at.desc())
    ).all()


@router.post("", response_model=TokenCreated, status_code=status.HTTP_201_CREATED)
def create_token(
    payload: TokenCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    live = db.scalar(select(func.count()).select_from(ApiToken).where(*_active(current_user.id)))
    if live >= settings.MAX_ACTIVE_TOKENS_PER_USER:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"You already have {live} active tokens. Revoke one you no longer use first.",
        )

    raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
    token = ApiToken(
        user_id=current_user.id,
        name=payload.name.strip(),
        token_hash=hash_token(raw),
        prefix=raw[:8],
        expires_at=utcnow() + timedelta(days=settings.TOKEN_TTL_DAYS),
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return TokenCreated(
        id=token.id,
        name=token.name,
        prefix=token.prefix,
        created_at=token.created_at,
        expires_at=token.expires_at,
        last_used_at=None,
        token=raw,
    )


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(
    token_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = db.scalar(
        select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == current_user.id)
    )
    # Someone else's token looks exactly like a missing one.
    if token is None or token.revoked_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token not found")
    token.revoked_at = utcnow()
    db.commit()
