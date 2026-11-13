from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.auth import end_user_sessions, hash_password, start_session
from app.config import settings
from app.db import get_db
from app.errors import ApiError
from app.models import Invite, User
from app.ratelimit import RateLimiter
from app.routers.admin import hash_invite_token, utcnow
from app.schemas import InviteAccept, InviteInfo, UserOut

# Public on purpose: the invitee has no account yet. The unguessable token
# in the link is the only credential.
router = APIRouter(prefix="/invites", tags=["invites"])

INVALID_INVITE = "This invitation link is invalid or has expired."

# The token is unguessable, so this only slows down noise and probing.
_limiter = RateLimiter(settings.INVITE_MAX_REQUESTS_PER_IP, settings.LOGIN_WINDOW_MINUTES * 60)


def _throttle(request: Request) -> None:
    key = request.client.host if request.client else "unknown"
    if not _limiter.allow(key):
        retry = _limiter.retry_after(key)
        raise ApiError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "too_many_attempts",
            "Too many requests. Try again later.",
            headers={"Retry-After": str(retry)},
            minutes=max(1, -(-retry // 60)),
        )


def _get_valid_invite(db: Session, token: str) -> Invite:
    invite = db.scalar(select(Invite).where(Invite.token_hash == hash_invite_token(token)))
    # Unknown, already used and expired all get the same answer: the invitee
    # can't act on the difference anyway (they need a new link either way).
    if invite is None or invite.accepted_at is not None or invite.expires_at <= utcnow():
        raise ApiError(status.HTTP_404_NOT_FOUND, "invite_invalid", INVALID_INVITE)
    return invite


@router.get("/{token}", response_model=InviteInfo)
def get_invite(token: str, request: Request, db: Session = Depends(get_db)):
    _throttle(request)
    invite = _get_valid_invite(db, token)
    return InviteInfo(email=invite.email, kind=invite.kind)


@router.post("/{token}/accept", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def accept_invite(
    token: str,
    payload: InviteAccept,
    request: Request,
    db: Session = Depends(get_db),
):
    _throttle(request)
    invite = _get_valid_invite(db, token)

    if len(payload.password) < settings.MIN_PASSWORD_LENGTH:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "password_too_short",
            f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters",
            min=settings.MIN_PASSWORD_LENGTH,
        )
    existing = db.scalar(select(User).where(User.email == invite.email))

    if invite.kind == "reset":
        # A password reset issued by an administrator: same person, new password.
        if existing is None or not existing.is_active:
            raise ApiError(status.HTTP_404_NOT_FOUND, "invite_invalid", INVALID_INVITE)
        existing.password_hash = hash_password(payload.password)
        end_user_sessions(db, existing.id)  # whoever had the old password is signed out
        invite.accepted_at = utcnow()
        audit.record(
            db, audit.PASSWORD_RESET_COMPLETED, actor=existing, target=existing.email, request=request
        )
        start_session(db, request, existing)
        db.commit()
        db.refresh(existing)
        return existing

    if existing is not None:
        raise ApiError(status.HTTP_409_CONFLICT, "email_taken", "A user with this email already exists")

    user = User(email=invite.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()  # assigns user.id for the audit entry
    invite.accepted_at = utcnow()
    audit.record(db, audit.INVITE_ACCEPTED, actor=user, target=user.email, request=request)
    # Log the new user straight in, the same way /auth/login does.
    start_session(db, request, user)
    db.commit()
    db.refresh(user)
    return user
