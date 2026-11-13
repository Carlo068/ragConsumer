import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_collection_role
from app.db import get_db
from app.models import AiMatterSelection, CollectionRole, User

router = APIRouter(prefix="/collections/{collection_id}/ai-access", tags=["ai-access"])


@router.put("", status_code=status.HTTP_204_NO_CONTENT)
def enable_ai_access(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Let my own AI search this matter. Needs at least viewer access, and a
    non-member can't tell the matter exists (404). Idempotent."""
    require_collection_role(db, current_user.id, collection_id, CollectionRole.viewer)
    if db.get(AiMatterSelection, (current_user.id, collection_id)) is None:
        db.add(AiMatterSelection(user_id=current_user.id, collection_id=collection_id))
        db.commit()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def disable_ai_access(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_collection_role(db, current_user.id, collection_id, CollectionRole.viewer)
    selection = db.get(AiMatterSelection, (current_user.id, collection_id))
    if selection is not None:
        db.delete(selection)
        db.commit()
