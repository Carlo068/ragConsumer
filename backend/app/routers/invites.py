from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.auth import hash_password
from app.config import settings
from app.db import get_db
from app.errors import ApiError
from app.models import Invite, User
from app.routers.admin import hash_invite_token, utcnow
from app.schemas import InviteAccept, InviteInfo, UserOut

# Public on purpose: the invitee has no account yet. The unguessable token
# in the link is the only credential.
router = APIRouter(prefix="/invites", tags=["invites"])

INVALID_INVITE = "This invitation link is invalid or has expired."


def _get_valid_invite(db: Session, token: str) -> Invite:
    invite = db.scalar(select(Invite).where(Invite.token_hash == hash_invite_token(token)))
    # Unknown, already used and expired all get the same answer: the invitee
    # can't act on the difference anyway (they need a new link either way).
    if invite is None or invite.accepted_at is not None or invite.expires_at <= utcnow():
        raise ApiError(status.HTTP_404_NOT_FOUND, "invite_invalid", INVALID_INVITE)
    return invite


@router.get("/{token}", response_model=InviteInfo)
def get_invite(token: str, db: Session = Depends(get_db)):
    return InviteInfo(email=_get_valid_invite(db, token).email)


@router.post("/{token}/accept", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def accept_invite(
    token: str,
    payload: InviteAccept,
    request: Request,
    db: Session = Depends(get_db),
):
    invite = _get_valid_invite(db, token)

    if len(payload.password) < settings.MIN_PASSWORD_LENGTH:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "password_too_short",
            f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters",
            min=settings.MIN_PASSWORD_LENGTH,
        )
    if db.scalar(select(User).where(User.email == invite.email)) is not None:
        raise ApiError(status.HTTP_409_CONFLICT, "email_taken", "A user with this email already exists")

    user = User(email=invite.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()  # assigns user.id for the audit entry
    invite.accepted_at = utcnow()
    audit.record(db, audit.INVITE_ACCEPTED, actor=user, target=user.email, request=request)
    db.commit()
    db.refresh(user)

    # Log the new user straight in, the same way /auth/login does.
    request.session.clear()
    request.session["user_id"] = str(user.id)
    return user
