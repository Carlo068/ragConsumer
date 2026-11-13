from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.auth import DUMMY_PASSWORD_HASH, get_current_user, verify_password
from app.db import get_db
from app.errors import ApiError
from app.models import User
from app.schemas import LoginRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    # Invites store emails lowercased, so match the same way: "Ana@Firm.mx"
    # and "ana@firm.mx" are the same account.
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    password_ok = verify_password(
        payload.password, user.password_hash if user else DUMMY_PASSWORD_HASH
    )
    if user is None or not password_ok:
        # Failed attempts are logged too: repeated failures on one address are
        # how a guessing attack shows up. The password is never recorded.
        audit.record(db, audit.LOGIN_FAILED, target=payload.email.lower(), request=request)
        db.commit()
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "invalid_credentials", "Invalid credentials")

    request.session.clear()
    request.session["user_id"] = str(user.id)
    audit.record(db, audit.LOGIN, actor=user, request=request)
    db.commit()
    return user


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user