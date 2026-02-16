"""
Document model for file management.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Integer, String, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"          # Uploaded, waiting for processing
    PROCESSING = "processing"    # Currently being processed
    COMPLETED = "completed"      # Processing complete
    FAILED = "failed"           # Processing failed
    ARCHIVED = "archived"       # Archived by user


class DocumentType(str, Enum):
    """Document type/category."""
    PDF = "pdf"
    WORD = "word"
    TEXT = "text"
    MARKDOWN = "markdown"
    OTHER = "other"


class Document(BaseModel):
    """
    Document model for uploaded files.
    
    Stores metadata about uploaded documents and their processing status.
    Actual files are stored in external storage (local filesystem or S3).
    """
    
    __tablename__ = "documents"
    
    # Basic metadata
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
        comment="Document title"
    )
    
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Document description"
    )
    
    # File metadata
    filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Original filename"
    )
    
    file_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Storage path (local or S3 key)"
    )
    
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="File size in bytes"
    )
    
    mime_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="MIME type (e.g., application/pdf)"
    )
    
    file_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="SHA256 hash for deduplication"
    )
    
    # Classification
    document_type: Mapped[DocumentType] = mapped_column(
        String(50),
        nullable=False,
        default=DocumentType.OTHER,
        index=True,
        comment="Document type"
    )
    
    # Status
    status: Mapped[DocumentStatus] = mapped_column(
        String(50),
        nullable=False,
        default=DocumentStatus.PENDING,
        index=True,
        comment="Processing status"
    )
    
    # Processing metadata
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When processing started"
    )
    
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When processing completed"
    )
    
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if processing failed"
    )
    
    # Content extraction (for future AI/ML features)
    text_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Extracted text content"
    )
    
    page_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of pages (for PDFs)"
    )
    
    # Flags
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Public access flag"
    )
    
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Soft delete flag"
    )
    
    # Ownership & tenant isolation
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant ID"
    )
    
    uploaded_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who uploaded the document"
    )
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    uploaded_by: Mapped["User"] = relationship("User")
    
    # Composite indexes for common queries
    __table_args__ = (
        Index("idx_document_tenant_status", "tenant_id", "status"),
        Index("idx_document_tenant_type", "tenant_id", "document_type"),
        Index("idx_document_tenant_created", "tenant_id", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title={self.title}, status={self.status})>"