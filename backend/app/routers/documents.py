import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_collection_membership
from app.config import settings
from app.db import get_db
from app.models import Document, User
from app.schemas import DocumentOut
from app.storage import BUCKET_NAME, delete_object, minio_client
from app.vectorstore import delete_document_chunks

router = APIRouter(prefix="/collections", tags=["documents"])


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
    require_collection_membership(db, current_user.id, collection_id)

    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File exceeds the {max_mb:.0f} MB upload limit",
        )

    doc_id = uuid.uuid4()
    object_key = f"collection-{collection_id}/doc-{doc_id}/{file.filename}"

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
    require_collection_membership(db, current_user.id, collection_id)

    documents = db.scalars(
        select(Document)
        .where(Document.collection_id == collection_id)
        .order_by(Document.created_at.desc())
    ).all()
    return documents


@router.delete(
    "/{collection_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_document(
    collection_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_collection_membership(db, current_user.id, collection_id)

    document = db.scalar(
        select(Document).where(
            Document.id == document_id, Document.collection_id == collection_id
        )
    )
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    delete_document_chunks(str(document_id))
    delete_object(document.object_key)

    db.delete(document)
    db.commit()
