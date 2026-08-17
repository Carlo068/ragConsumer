from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_collection_membership
from app.db import get_db
from app.models import Collection, McpActiveCollection, User
from app.schemas import McpActiveCollectionOut, McpActiveCollectionSet

router = APIRouter(prefix="/mcp", tags=["mcp"])


def _load(db: Session) -> McpActiveCollectionOut:
    row = db.get(McpActiveCollection, 1)
    if row is None or row.collection_id is None:
        return McpActiveCollectionOut(collection_id=None, collection_name=None)
    collection = db.get(Collection, row.collection_id)
    return McpActiveCollectionOut(
        collection_id=row.collection_id,
        collection_name=collection.name if collection else None,
    )


@router.get("/active-collection", response_model=McpActiveCollectionOut)
def get_active_collection(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _load(db)


@router.put("/active-collection", response_model=McpActiveCollectionOut)
def set_active_collection(
    payload: McpActiveCollectionSet,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.collection_id is not None:
        require_collection_membership(db, current_user.id, payload.collection_id)

    row = db.get(McpActiveCollection, 1)
    if row is None:
        row = McpActiveCollection(id=1, collection_id=payload.collection_id)
        db.add(row)
    else:
        row.collection_id = payload.collection_id
    db.commit()

    return _load(db)
