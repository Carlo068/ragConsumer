import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_collection_membership
from app.db import get_db
from app.models import Collection, CollectionMember, Document, User
from app.schemas import CollectionCreate, CollectionOut, CollectionUpdate
from app.storage import delete_objects_by_prefix
from app.vectorstore import delete_document_chunks

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


@router.post("", response_model=CollectionOut, status_code=status.HTTP_201_CREATED)
def create_collection(
    payload: CollectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collection = Collection(name=payload.name)
    db.add(collection)
    db.flush()  # populate collection.id before referencing it below
    db.add(CollectionMember(user_id=current_user.id, collection_id=collection.id))
    db.commit()
    db.refresh(collection)
    return collection


@router.patch("/{collection_id}", response_model=CollectionOut)
def rename_collection(
    collection_id: uuid.UUID,
    payload: CollectionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_collection_membership(db, current_user.id, collection_id)

    collection = db.get(Collection, collection_id)
    if collection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Collection not found")

    collection.name = payload.name
    db.commit()
    db.refresh(collection)
    return collection


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_collection_membership(db, current_user.id, collection_id)

    collection = db.get(Collection, collection_id)
    if collection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Collection not found")

    # Clean up MinIO + Qdrant *before* the Postgres cascade removes the only
    # record that these documents ever existed -- neither system is FK-linked
    # to Postgres, so nothing does this automatically.
    document_ids = db.scalars(
        select(Document.id).where(Document.collection_id == collection_id)
    ).all()
    for doc_id in document_ids:
        delete_document_chunks(str(doc_id))
    delete_objects_by_prefix(f"collection-{collection_id}/")

    db.delete(collection)  # cascades collection_members + documents rows
    db.commit()
