from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Case, CaseLawyer, User
from app.schemas import CaseOut

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=list[CaseOut])
def list_cases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cases = db.scalars(
        select(Case)
        .join(CaseLawyer, CaseLawyer.case_id == Case.id)
        .where(CaseLawyer.user_id == current_user.id)
        .order_by(Case.name)
    ).all()
    return cases