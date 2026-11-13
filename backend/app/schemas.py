import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import CollectionRole, DocumentStatus


# Long enough for any passphrase; short enough that hashing it is not a DoS.
MAX_PASSWORD_LENGTH = 256


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    is_admin: bool

    class Config:
        from_attributes = True


class AdminUserOut(UserOut):
    created_at: datetime
    is_active: bool


class ChangePassword(BaseModel):
    current_password: str = Field(max_length=MAX_PASSWORD_LENGTH)
    new_password: str = Field(max_length=MAX_PASSWORD_LENGTH)


class InviteCreate(BaseModel):
    email: EmailStr


class InviteOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    created_at: datetime
    expires_at: datetime
    kind: str = "invite"  # "invite" (new account) or "reset" (new password)

    class Config:
        from_attributes = True


class InviteCreated(InviteOut):
    # Returned once, at creation. Only the token's hash is stored, so this
    # link can't be retrieved again later; re-inviting issues a fresh one.
    invite_url: str


class InviteInfo(BaseModel):
    email: EmailStr
    kind: str = "invite"


class InviteAccept(BaseModel):
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)


class CollectionOut(BaseModel):
    id: uuid.UUID
    name: str
    # The requesting user's own role on this collection. The UI uses it to
    # hide actions they can't perform; the server enforces it regardless.
    role: CollectionRole
    # Whether this person's own AI currently searches this matter.
    ai_enabled: bool
    # File counts for the list ("12 files, 10 ready").
    document_count: int = 0
    ready_count: int = 0
    failed_count: int = 0

    class Config:
        from_attributes = True


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class CollectionUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: EmailStr
    role: CollectionRole


class MemberAdd(BaseModel):
    email: EmailStr
    role: CollectionRole


class MemberRoleUpdate(BaseModel):
    role: CollectionRole


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class TokenOut(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None

    class Config:
        from_attributes = True


class TokenCreated(TokenOut):
    # Shown exactly once. Only a hash is stored, so it can't be retrieved later.
    token: str


class DocumentOut(BaseModel):
    id: uuid.UUID
    collection_id: uuid.UUID
    source_filename: str
    status: DocumentStatus
    error_message: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditEntryOut(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    actor_email: str | None
    action: str
    collection_id: uuid.UUID | None
    collection_name: str | None
    target: str | None
    detail: dict | None
    ip: str | None

    class Config:
        from_attributes = True


class AuditPage(BaseModel):
    items: list[AuditEntryOut]
    total: int
