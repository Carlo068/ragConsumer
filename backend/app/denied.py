"""Writes a refused matter request to the audit log.

A person asking for a matter they do not belong to (404) or an action their role
does not allow (403) is exactly what someone probing the system looks like, and
what a firm with ethical walls wants to be able to see afterwards. The request
itself is refused as before; this only adds the record. It never makes the
response fail: if the record cannot be written the person still gets their answer."""

import uuid

from fastapi import Request

from app import audit
from app.db import SessionLocal
from app.models import User, UserSession

# Refusals about matters. (Not 401: someone who is not signed in is nobody to record.)
DENIED_CODES = {"matter_not_found", "role_required"}


def record_denied(request: Request, code: str, status_code: int) -> None:
    try:
        sid = request.session.get("sid")
        if not sid:
            return
        with SessionLocal() as db:
            session = db.get(UserSession, uuid.UUID(sid))
            if session is None or session.ended_at is not None:
                return
            user = db.get(User, session.user_id)
            if user is None or not user.is_active:
                return
            collection_id = None
            raw = request.scope.get("path_params", {}).get("collection_id")
            if raw:
                try:
                    collection_id = uuid.UUID(str(raw))
                except ValueError:
                    pass
            audit.record(
                db,
                audit.ACCESS_DENIED,
                actor=user,
                collection_id=collection_id,
                target=f"{request.method} {request.url.path}"[:1000],
                detail={"code": code, "status": status_code},
                request=request,
            )
            db.commit()
    except Exception as exc:  # never turn a refusal into a server error
        print(f"Could not record a refused request: {exc}")
