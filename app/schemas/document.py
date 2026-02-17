"""
Pydantic schemas for Document.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.models.document import DocumentStatus, DocumentType
from app.schemas.common import BaseSchema


class DocumentBase(BaseSchema):
    """Base document schema."""
    
    title: str = Field(..., min_length=1, max_length=500, description="Document title")
    description: str | None = Field(None, max_length=5000, description="Document description")


class DocumentCreate(DocumentBase):
    """Schema for document creation (used internally)."""
    
    filename: str
    file_path: str
    file_size: int
    mime_type: str
    file_hash: str | None = None
    document_type: DocumentType
    tenant_id: str
    uploaded_by_user_id: str


class DocumentUpdate(BaseSchema):
    """Schema for updating document metadata."""
    
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = Field(None, max_length=5000)
    status: DocumentStatus | None = None
    is_public: bool | None = None


class DocumentRead(DocumentBase):
    """Schema for reading document data."""
    
    id: str
    filename: str
    file_size: int
    mime_type: str
    document_type: DocumentType
    status: DocumentStatus
    is_public: bool
    is_deleted: bool
    page_count: int | None
    tenant_id: str
    uploaded_by_user_id: str | None
    processing_started_at: datetime | None
    processing_completed_at: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    
    @property
    def file_url(self) -> str:
        """Generate file download URL."""
        return f"/api/v1/documents/{self.id}/download"


class DocumentUploadResponse(BaseSchema):
    """Response after successful upload."""
    
    document: DocumentRead
    task_id: str = Field(..., description="Background processing task ID")
    message: str = "Document uploaded successfully. Processing in background."


class DocumentFilter(BaseSchema):
    """Query parameters for filtering documents."""
    
    status: DocumentStatus | None = None
    document_type: DocumentType | None = None
    search: str | None = Field(None, max_length=200, description="Search in title and description")
    uploaded_by_user_id: str | None = None
    is_deleted: bool = False
    
    # Date range filters
    created_after: datetime | None = None
    created_before: datetime | None = None
    
    # Sorting
    sort_by: Literal["created_at", "updated_at", "title", "file_size"] = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"


class DocumentStats(BaseSchema):
    """Document statistics for a tenant."""
    
    total_documents: int
    total_size_bytes: int
    total_size_mb: float
    by_status: dict[str, int]
    by_type: dict[str, int]
    recent_uploads: int  # Last 7 days