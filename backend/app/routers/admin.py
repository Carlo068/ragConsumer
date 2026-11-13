import csv
import hashlib
import io
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import audit
from app.auth import require_admin
from app.config import settings
from app.db import get_db
from app.models import AuditLog, Invite, User
from app.schemas import (
    AdminUserOut,
    AuditEntryOut,
    AuditPage,
    InviteCreate,
    InviteCreated,
    InviteOut,
)

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
    audit.record(db, audit.INVITE_CREATED, actor=admin, target=email)
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
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    invite = db.get(Invite, invite_id)
    if invite is None or invite.accepted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    audit.record(db, audit.INVITE_REVOKED, actor=admin, target=invite.email)
    db.delete(invite)
    db.commit()


def _audit_filters(
    action: str | None, collection_id: uuid.UUID | None, actor: str | None
) -> list:
    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if collection_id:
        filters.append(AuditLog.collection_id == collection_id)
    if actor:
        filters.append(func.lower(AuditLog.actor_email).contains(actor.lower()))
    return filters


@router.get("/audit", response_model=AuditPage)
def list_audit(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = None,
    collection_id: uuid.UUID | None = None,
    actor: str | None = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Newest first. Read-only: nothing in the app can change or remove entries."""
    filters = _audit_filters(action, collection_id, actor)
    # Reading the log is itself recorded. Only the first page of a browse is
    # logged, so paging through doesn't flood the log with its own reads.
    if offset == 0:
        audit.record(
            db, audit.AUDIT_VIEWED, actor=admin,
            detail={k: v for k, v in {"action": action, "actor": actor,
                                      "collection_id": str(collection_id) if collection_id else None}.items() if v},
        )
        db.commit()
    total = db.scalar(select(func.count()).select_from(AuditLog).where(*filters))
    items = db.scalars(
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.occurred_at.desc(), AuditLog.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return AuditPage(items=[AuditEntryOut.model_validate(i) for i in items], total=total)


UTF8_BOM = chr(0xFEFF)  # so Excel reads accents correctly
CSV_COLUMNS = ["occurred_at_utc", "actor", "action", "matter", "target", "detail", "ip"]


def _csv_cell(value) -> str:
    text = "" if value is None else str(value)
    # A spreadsheet treats a cell starting with = + - @ as a formula. Entries
    # contain text people control (search queries, filenames), so defuse it.
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/audit.csv")
def export_audit_csv(
    action: str | None = None,
    collection_id: uuid.UUID | None = None,
    actor: str | None = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    filters = _audit_filters(action, collection_id, actor)
    audit.record(
        db, audit.AUDIT_EXPORTED, actor=admin,
        detail={k: v for k, v in {"action": action, "actor": actor,
                                  "collection_id": str(collection_id) if collection_id else None}.items() if v},
    )
    db.commit()

    def rows():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(CSV_COLUMNS)
        yield UTF8_BOM + buffer.getvalue()  # BOM so Excel reads accents correctly
        query = select(AuditLog).where(*filters).order_by(AuditLog.occurred_at.desc(), AuditLog.id)
        for entry in db.scalars(query).yield_per(500):
            buffer.seek(0)
            buffer.truncate()
            writer.writerow(
                _csv_cell(v)
                for v in (
                    entry.occurred_at.isoformat(sep=" ", timespec="seconds"),
                    entry.actor_email,
                    entry.action,
                    entry.collection_name,
                    entry.target,
                    json.dumps(entry.detail, ensure_ascii=False) if entry.detail else "",
                    entry.ip,
                )
            )
            yield buffer.getvalue()

    return StreamingResponse(
        rows(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit-log.csv"'},
    )
