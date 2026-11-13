from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.auth import (
    DUMMY_PASSWORD_HASH,
    end_session,
    end_user_sessions,
    get_current_user,
    hash_password,
    start_session,
    utcnow,
    verify_password,
)
from app.config import settings
from app.db import get_db
from app.errors import ApiError
from app.models import AuditLog, User
from app.schemas import ChangePassword, LoginRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _check_not_throttled(db: Session, request: Request, email: str) -> None:
    """Pauses sign-in after too many recent failures for this account or from
    this address. Counted in the audit log, so it survives a restart. While
    paused even the right password is refused; the pause ends by itself.

    The pause itself is recorded once per window, not once per attempt, so an
    attacker cannot fill the log by hammering a paused account."""
    window_start = utcnow() - timedelta(minutes=settings.LOGIN_WINDOW_MINUTES)
    ip = request.client.host if request.client else None

    failures = select(func.count()).select_from(AuditLog).where(
        AuditLog.action == audit.LOGIN_FAILED, AuditLog.occurred_at >= window_start
    )
    account_failures = db.scalar(failures.where(AuditLog.target == email)) or 0
    address_failures = (db.scalar(failures.where(AuditLog.ip == ip)) or 0) if ip else 0

    if (
        account_failures < settings.LOGIN_MAX_FAILURES_PER_ACCOUNT
        and address_failures < settings.LOGIN_MAX_FAILURES_PER_IP
    ):
        return

    already_recorded = db.scalar(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == audit.LOGIN_THROTTLED,
            AuditLog.target == email,
            AuditLog.occurred_at >= window_start,
        )
    )
    if not already_recorded:
        audit.record(
            db, audit.LOGIN_THROTTLED, target=email, request=request,
            detail={"account_failures": account_failures, "address_failures": address_failures},
        )
        db.commit()
    raise ApiError(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "too_many_attempts",
        "Too many failed attempts. Try again later.",
        headers={"Retry-After": str(settings.LOGIN_WINDOW_MINUTES * 60)},
        minutes=settings.LOGIN_WINDOW_MINUTES,
    )


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    # Invites store emails lowercased, so match the same way: "Ana@Firm.mx"
    # and "ana@firm.mx" are the same account.
    email = payload.email.lower()
    _check_not_throttled(db, request, email)

    user = db.scalar(select(User).where(User.email == email))
    password_ok = verify_password(
        payload.password, user.password_hash if user else DUMMY_PASSWORD_HASH
    )
    if user is None or not password_ok or not user.is_active:
        # Failed attempts are logged too: repeated failures on one address are
        # how a guessing attack shows up. The password is never recorded. A
        # disabled account gets the same answer as a wrong password, so the
        # screen does not reveal which accounts exist.
        disabled = user is not None and password_ok and not user.is_active
        audit.record(
            db, audit.LOGIN_FAILED, target=email, request=request,
            detail={"reason": "account_disabled"} if disabled else None,
        )
        db.commit()
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "invalid_credentials", "Invalid credentials")

    start_session(db, request, user)
    audit.record(db, audit.LOGIN, actor=user, request=request)
    db.commit()
    return user


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    # Ends the session on the server, not just the cookie in this browser, so a
    # copy of the cookie stops working too.
    end_session(db, request)
    db.commit()
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePassword,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Changes the signed-in person's password and signs them out everywhere else."""
    _check_not_throttled(db, request, current_user.email)

    if not verify_password(payload.current_password, current_user.password_hash):
        # Counted like a failed sign-in, so a stolen session cannot be used to
        # guess the password without limit.
        audit.record(
            db, audit.LOGIN_FAILED, target=current_user.email, request=request,
            detail={"via": "change_password"},
        )
        db.commit()
        raise ApiError(status.HTTP_400_BAD_REQUEST, "wrong_password", "The current password is not correct")
    if len(payload.new_password) < settings.MIN_PASSWORD_LENGTH:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "password_too_short",
            f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters",
            min=settings.MIN_PASSWORD_LENGTH,
        )

    current_user.password_hash = hash_password(payload.new_password)
    ended = end_user_sessions(db, current_user.id, except_session=request.state.session_id)
    audit.record(
        db, audit.PASSWORD_CHANGED, actor=current_user, request=request,
        detail={"other_sessions_ended": ended},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
