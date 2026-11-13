import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum as SqlEnum, ForeignKey, String, false
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Account management only (inviting users). Grants no access to any
    # matter: an admin sees a collection only by being a member of it, so
    # ethical walls between matters hold even for the person running the firm.
    is_admin: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    collection_links: Mapped[list["CollectionMember"]] = relationship(
        back_populates="user", passive_deletes=True
    )


class Invite(Base):
    """A pending invitation. Accounts are invite-only, so this is the only
    way a new user gets created outside the admin bootstrap script."""

    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), index=True)
    # SHA-256 of the token in the invite link. The raw token is shown to the
    # admin once and never stored, so a database leak can't be replayed into
    # account takeover.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    member_links: Mapped[list["CollectionMember"]] = relationship(
        back_populates="collection", passive_deletes=True
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="collection", passive_deletes=True
    )


class CollectionRole(str, enum.Enum):
    """What someone may do inside one matter. Roles are per matter: the same
    person can own one matter and merely view another."""

    viewer = "viewer"  # search through their AI, and see the file list
    editor = "editor"  # also upload and delete files
    owner = "owner"  # also rename/delete the matter and manage its members


# Higher number = more permissions. Kept next to the enum so "at least editor"
# is one comparison everywhere instead of ad-hoc lists of allowed roles.
ROLE_RANK = {CollectionRole.viewer: 1, CollectionRole.editor: 2, CollectionRole.owner: 3}


class CollectionMember(Base):
    __tablename__ = "collection_members"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    # Deliberately no default: every place that grants access must say which
    # role, so a forgotten argument fails loudly instead of quietly handing
    # out the wrong permissions.
    role: Mapped[CollectionRole] = mapped_column(
        SqlEnum(CollectionRole, name="collection_role")
    )
    granted_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="collection_links")
    collection: Mapped["Collection"] = relationship(back_populates="member_links")


class DocumentStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), index=True
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    source_filename: Mapped[str] = mapped_column(String(512))
    object_key: Mapped[str] = mapped_column(String(1024))
    status: Mapped[DocumentStatus] = mapped_column(
        SqlEnum(DocumentStatus, name="document_status"),
        default=DocumentStatus.uploaded,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    collection: Mapped["Collection"] = relationship(back_populates="documents")


class McpActiveCollection(Base):
    """Singleton row (id is always 1): which collection the one shared MCP
    server currently exposes. Read fresh by mcp_server on every tool call, so
    toggling it here takes effect immediately with no restart."""

    __tablename__ = "mcp_active_collection"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("collections.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class ApiToken(Base):
    """A personal access token for the MCP server. Lets one person's AI
    assistant act as that person, and nothing more: it carries the user's own
    permissions, never an admin's."""

    __tablename__ = "api_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    # SHA-256 of the token. The raw token is shown once at creation and never
    # stored, so a database leak yields nothing usable. The token is 256 bits
    # of randomness, so a plain fast hash is enough (no password-style KDF).
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # First characters of the token, so a person can tell their tokens apart
    # in the list without the list ever containing a usable secret.
    prefix: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
