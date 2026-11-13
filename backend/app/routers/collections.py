import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.auth import get_current_user, require_collection_role
from app.db import get_db
from app.models import (
    AiMatterSelection,
    Collection,
    CollectionMember,
    CollectionRole,
    Document,
    User,
)
from app.schemas import CollectionCreate, CollectionOut, CollectionUpdate
from app.storage import delete_objects_by_prefix
from app.vectorstore import delete_matter_vectors

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("", response_model=list[CollectionOut])
def list_collections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Collection, CollectionMember.role, AiMatterSelection.collection_id)
        .join(CollectionMember, CollectionMember.collection_id == Collection.id)
        .outerjoin(
            AiMatterSelection,
            (AiMatterSelection.collection_id == Collection.id)
            & (AiMatterSelection.user_id == current_user.id),
        )
        .where(CollectionMember.user_id == current_user.id)
        .order_by(Collection.name)
    ).all()
    return [
        CollectionOut(id=c.id, name=c.name, role=role, ai_enabled=selected is not None)
        for c, role, selected in rows
    ]


@router.post("", response_model=CollectionOut, status_code=status.HTTP_201_CREATED)
def create_collection(
    payload: CollectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collection = Collection(name=payload.name)
    db.add(collection)
    db.flush()  # populate collection.id before referencing it below
    # Whoever creates a matter owns it.
    db.add(
        CollectionMember(
            user_id=current_user.id, collection_id=collection.id, role=CollectionRole.owner
        )
    )
    audit.record(
        db, audit.MATTER_CREATED, actor=current_user,
        collection_id=collection.id, collection_name=collection.name,
    )
    db.commit()
    db.refresh(collection)
    return CollectionOut(
        id=collection.id, name=collection.name, role=CollectionRole.owner, ai_enabled=False
    )


@router.patch("/{collection_id}", response_model=CollectionOut)
def rename_collection(
    collection_id: uuid.UUID,
    payload: CollectionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = require_collection_role(db, current_user.id, collection_id, CollectionRole.owner)

    collection = db.get(Collection, collection_id)
    if collection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Collection not found")

    previous_name = collection.name
    collection.name = payload.name
    audit.record(
        db, audit.MATTER_RENAMED, actor=current_user,
        collection_id=collection.id, collection_name=payload.name,
        detail={"previous_name": previous_name},
    )
    db.commit()
    db.refresh(collection)
    ai_enabled = db.get(AiMatterSelection, (current_user.id, collection_id)) is not None
    return CollectionOut(
        id=collection.id, name=collection.name, role=member.role, ai_enabled=ai_enabled
    )


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_collection_role(db, current_user.id, collection_id, CollectionRole.owner)

    collection = db.get(Collection, collection_id)
    if collection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Collection not found")

    # Clean up Qdrant + MinIO *before* the Postgres cascade removes the only
    # record that this matter ever existed -- neither system is FK-linked to
    # Postgres, so nothing does this automatically. A matter owns its whole
    # Qdrant collection, so this is a single drop.
    delete_matter_vectors(str(collection_id))
    delete_objects_by_prefix(f"collection-{collection_id}/")

    audit.record(
        db, audit.MATTER_DELETED, actor=current_user,
        collection_id=collection.id, collection_name=collection.name,
    )
    db.delete(collection)  # cascades collection_members + documents rows
    db.commit()
