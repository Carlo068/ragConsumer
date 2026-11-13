import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import DocumentStatus


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    is_admin: bool

    class Config:
        from_attributes = True


class AdminUserOut(UserOut):
    created_at: datetime


class InviteCreate(BaseModel):
    email: EmailStr


class InviteOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


class InviteCreated(InviteOut):
    # Returned once, at creation. Only the token's hash is stored, so this
    # link can't be retrieved again later; re-inviting issues a fresh one.
    invite_url: str


class InviteInfo(BaseModel):
    email: EmailStr


class InviteAccept(BaseModel):
    password: str


class CollectionOut(BaseModel):
    id: uuid.UUID
    name: str

    class Config:
        from_attributes = True


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class CollectionUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class McpActiveCollectionOut(BaseModel):
    collection_id: uuid.UUID | None
    collection_name: str | None


class McpActiveCollectionSet(BaseModel):
    collection_id: uuid.UUID | None


class DocumentOut(BaseModel):
    id: uuid.UUID
    collection_id: uuid.UUID
    source_filename: str
    status: DocumentStatus
    created_at: datetime

    class Config:
        from_attributes = True