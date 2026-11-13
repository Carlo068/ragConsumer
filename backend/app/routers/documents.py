import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.auth import get_current_user, require_collection_role
from app.config import settings
from app.db import get_db
from app.models import CollectionRole, Document, DocumentStatus, User
from app.schemas import DocumentOut
from app.storage import BUCKET_NAME, delete_object, minio_client
from app.vectorstore import delete_document_chunks

router = APIRouter(prefix="/collections", tags=["documents"])

MAX_FILENAME_LENGTH = 255


def safe_filename(raw: str | None) -> str:
    """A filename that is safe to put in a storage key and show to people:
    no directory part, no control characters, never empty, at most 255 long
    (keeping the extension)."""
    name = (raw or "").replace(chr(92), "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable()).strip().lstrip(".")
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The file needs a name")
    if len(name) > MAX_FILENAME_LENGTH:
        stem, dot, extension = name.rpartition(".")
        extension = (dot + extension) if dot and len(extension) <= 10 else ""
        name = name[: MAX_FILENAME_LENGTH - len(extension)] + extension
    return name


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
    require_collection_role(db, current_user.id, collection_id, CollectionRole.editor)

    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File exceeds the {max_mb:.0f} MB upload limit",
        )

    filename = safe_filename(file.filename)
    doc_id = uuid.uuid4()
    object_key = f"collection-{collection_id}/doc-{doc_id}/{filename}"

    minio_client.put_object(
        BUCKET_NAME,
        object_key,
        io.BytesIO(contents),
        length=len(contents),
        content_type=file.content_type or "application/octet-stream",
    )

    try:
        document = Document(
            id=doc_id,
            collection_id=collection_id,
            uploaded_by=current_user.id,
            source_filename=filename,
            object_key=object_key,
        )
        db.add(document)
        audit.record(
            db, audit.DOCUMENT_UPLOADED, actor=current_user, collection_id=collection_id,
            target=filename, detail={"document_id": str(doc_id), "bytes": len(contents)},
        )
        db.commit()
    except Exception:
        # The object is already in storage and storage tells the worker about
        # it. Without its database row it would be indexed, searchable and
        # impossible to delete, so take it back out.
        db.rollback()
        delete_object(object_key)
        raise
    db.refresh(document)
    return document


@router.get("/{collection_id}/documents", response_model=list[DocumentOut])
def list_documents(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_collection_role(db, current_user.id, collection_id, CollectionRole.viewer)

    documents = db.scalars(
        select(Document)
        .where(Document.collection_id == collection_id)
        .order_by(Document.created_at.desc())
    ).all()
    return documents


@router.post(
    "/{collection_id}/documents/{document_id}/reingest", response_model=DocumentOut
)
def reingest_document(
    collection_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Try indexing a file again (the Retry button). Puts it back in the worker's
    queue and clears any earlier failure reason. Editors and above, like upload."""
    require_collection_role(db, current_user.id, collection_id, CollectionRole.editor)

    document = db.scalar(
        select(Document).where(
            Document.id == document_id, Document.collection_id == collection_id
        )
    )
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    if document.status == DocumentStatus.processing:
        # Being worked on right now. If it is truly stuck the worker's timeout
        # marks it failed, and then it can be retried.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This file is being processed right now. Try again in a moment."
        )

    # Drop what was indexed before so a retry can't leave stale passages behind.
    delete_document_chunks(str(collection_id), str(document_id))
    document.status = DocumentStatus.uploaded
    document.error_message = None
    audit.record(
        db, audit.DOCUMENT_REINGESTED, actor=current_user, collection_id=collection_id,
        target=document.source_filename, detail={"document_id": str(document_id)},
    )
    db.commit()
    db.refresh(document)
    return document


@router.delete(
    "/{collection_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_document(
    collection_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_collection_role(db, current_user.id, collection_id, CollectionRole.editor)

    document = db.scalar(
        select(Document).where(
            Document.id == document_id, Document.collection_id == collection_id
        )
    )
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    delete_document_chunks(str(collection_id), str(document_id))
    delete_object(document.object_key)

    audit.record(
        db, audit.DOCUMENT_DELETED, actor=current_user, collection_id=collection_id,
        target=document.source_filename, detail={"document_id": str(document_id)},
    )
    db.delete(document)
    db.commit()
