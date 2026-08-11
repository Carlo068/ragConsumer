import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum as SqlEnum, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    case_links: Mapped[list["CaseLawyer"]] = relationship(back_populates="user")


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    lawyer_links: Mapped[list["CaseLawyer"]] = relationship(back_populates="case")
    documents: Mapped[list["Document"]] = relationship(back_populates="case")


class CaseLawyer(Base):
    __tablename__ = "case_lawyers"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True
    )
    granted_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="case_links")
    case: Mapped["Case"] = relationship(back_populates="lawyer_links")


class DocumentStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True
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

    case: Mapped["Case"] = relationship(back_populates="documents")
