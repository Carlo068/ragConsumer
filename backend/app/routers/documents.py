import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import CollectionMember, Document, User
from app.schemas import DocumentOut
from app.storage import BUCKET_NAME, minio_client

router = APIRouter(prefix="/collections", tags=["documents"])


def _require_membership(db: Session, user_id: uuid.UUID, collection_id: uuid.UUID) -> None:
    member = db.scalar(
        select(CollectionMember).where(
            CollectionMember.user_id == user_id,
            CollectionMember.collection_id == collection_id,
        )
    )
    if member is None:
        # 404, not 403 — don't reveal whether the collection exists at all
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Collection not found")


@router.post(
    "/{collection_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    collection_id: uuid.UUID,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_membership(db, current_user.id, collection_id)

    doc_id = uuid.uuid4()
    object_key = f"collection-{collection_id}/doc-{doc_id}/{file.filename}"

    contents = await file.read()
    minio_client.put_object(
        BUCKET_NAME,
        object_key,
        io.BytesIO(contents),
        length=len(contents),
        content_type=file.content_type or "application/octet-stream",
    )

    document = Document(
        id=doc_id,
        collection_id=collection_id,
        uploaded_by=current_user.id,
        source_filename=file.filename,
        object_key=object_key,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get("/{collection_id}/documents", response_model=list[DocumentOut])
def list_documents(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_membership(db, current_user.id, collection_id)

    documents = db.scalars(
        select(Document)
        .where(Document.collection_id == collection_id)
        .order_by(Document.created_at.desc())
    ).all()
    return documents
