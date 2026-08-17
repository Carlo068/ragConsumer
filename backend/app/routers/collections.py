from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Collection, CollectionMember, User
from app.schemas import CollectionOut

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("", response_model=list[CollectionOut])
def list_collections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collections = db.scalars(
        select(Collection)
        .join(CollectionMember, CollectionMember.collection_id == Collection.id)
        .where(CollectionMember.user_id == current_user.id)
        .order_by(Collection.name)
    ).all()
    return collections
