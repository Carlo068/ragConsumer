import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.config import settings
from app.db import get_db
from app.models import Invite, User
from app.schemas import AdminUserOut, InviteCreate, InviteCreated, InviteOut

router = APIRouter(prefix="/admin", tags=["admin"])


def utcnow() -> datetime:
    # Naive UTC, to match the timestamp-without-time-zone columns.
    return datetime.now(UTC).replace(tzinfo=None)


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.scalars(select(User).order_by(User.email)).all()


@router.get("/invites", response_model=list[InviteOut])
def list_pending_invites(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(Invite)
        .where(Invite.accepted_at.is_(None), Invite.expires_at > utcnow())
        .order_by(Invite.created_at.desc())
    ).all()


@router.post("/invites", response_model=InviteCreated, status_code=status.HTTP_201_CREATED)
def create_invite(
    payload: InviteCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists")

    # Re-inviting replaces any earlier unaccepted invite, so only the newest
    # link works. An old link forwarded somewhere can't be used later.
    db.execute(delete(Invite).where(Invite.email == email, Invite.accepted_at.is_(None)))

    token = secrets.token_urlsafe(32)
    invite = Invite(
        email=email,
        token_hash=hash_invite_token(token),
        invited_by=admin.id,
        expires_at=utcnow() + timedelta(hours=settings.INVITE_TTL_HOURS),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    return InviteCreated(
        id=invite.id,
        email=invite.email,
        created_at=invite.created_at,
        expires_at=invite.expires_at,
        invite_url=f"{settings.FRONTEND_URL}/invite/{token}",
    )


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invite(
    invite_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    invite = db.get(Invite, invite_id)
    if invite is None or invite.accepted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    db.delete(invite)
    db.commit()
