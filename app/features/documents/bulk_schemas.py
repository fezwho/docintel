"""
Bulk operation schemas.
"""

from typing import Literal

from pydantic import Field

from app.models.document import DocumentStatus
from app.schemas.common import BaseSchema


class BulkDocumentAction(BaseSchema):
    """Schema for bulk document operations."""
    
    document_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of document IDs (max 100)"
    )
    
    action: Literal["delete", "archive", "restore", "reprocess"] = Field(
        ...,
        description="Action to perform on selected documents"
    )


class BulkOperationResult(BaseSchema):
    """Result of a bulk operation."""
    
    total_requested: int
    succeeded: int
    failed: int
    skipped: int
    errors: list[dict] = Field(
        default_factory=list,
        description="Errors for failed operations"
    )
    
    @property
    def success_rate(self) -> float:
        """Calculate success percentage."""
        if self.total_requested == 0:
            return 0.0
        return round(self.succeeded / self.total_requested * 100, 2)


class BulkUpdateSchema(BaseSchema):
    """Schema for bulk metadata update."""
    
    document_ids: list[str] = Field(..., min_length=1, max_length=100)
    updates: dict = Field(
        ...,
        description="Fields to update (e.g., {'is_public': true})"
    )