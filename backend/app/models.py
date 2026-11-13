import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Enum as SqlEnum, ForeignKey, String, false, true
from sqlalchemy.dialects.postgresql import JSONB
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
    # False means the person can no longer sign in, and neither can their AI
    # access keys. Set by an administrator when someone leaves the firm.
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    collection_links: Mapped[list["CollectionMember"]] = relationship(
        back_populates="user", passive_deletes=True
    )


class UserSession(Base):
    """One sign-in. The browser's cookie only carries this row's id, so a session
    can be ended on the server (sign out, an administrator disabling the
    account, a password change) and a copied cookie stops working at once."""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))


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
    # "invite": creates a new account. "reset": sets a new password on an
    # existing account (issued by an administrator when someone is locked out).
    kind: Mapped[str] = mapped_column(String(16), default="invite", server_default="invite")


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
    # Why indexing failed, in plain words for the person who uploaded it. Set by
    # the worker when status becomes "failed", cleared when the file is retried.
    error_message: Mapped[str | None] = mapped_column(String(1024), default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    collection: Mapped["Collection"] = relationship(back_populates="documents")


class AiMatterSelection(Base):
    """A matter this person has chosen to let their own AI search. Chosen per
    person, so one lawyer's choice never changes what a colleague's AI sees.

    This is a preference, not a permission: the MCP server only honours a row
    while the person is still a member of the matter, so removing someone from
    a matter cuts their AI off immediately whatever rows remain here."""

    __tablename__ = "ai_matter_selections"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    selected_at: Mapped[datetime] = mapped_column(server_default=func.now())


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


class AuditLog(Base):
    """Who did what to which matter, and when. Append-only: the application
    only ever inserts, and in Postgres a trigger rejects any UPDATE or DELETE.

    Deliberately no foreign keys. An entry has to stay true after the user or
    matter it names is deleted, so names are copied in and the ids are plain
    values."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    actor_user_id: Mapped[uuid.UUID | None]
    actor_email: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(64), index=True)
    collection_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    collection_name: Mapped[str | None] = mapped_column(String(255))
    # What the action was about: a filename, an email address, a token name.
    target: Mapped[str | None] = mapped_column(String(1024))
    # Extra structured facts, e.g. an AI search's query and returned chunk ids.
    detail: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    ip: Mapped[str | None] = mapped_column(String(64))
