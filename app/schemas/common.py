"""
Common/shared Pydantic schemas.
"""

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


# Base configuration for all schemas
class BaseSchema(BaseModel):
    """
    Base schema with common configuration.
    
    All schemas should inherit from this.
    """
    
    model_config = ConfigDict(
        from_attributes=True,  # Allow ORM mode (SQLAlchemy objects)
        populate_by_name=True,  # Allow population by field name or alias
        str_strip_whitespace=True,  # Strip whitespace from strings
        validate_assignment=True,  # Validate on assignment, not just creation
    )


# Pagination schema
class PaginationParams(BaseModel):
    """Query parameters for pagination."""
    
    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(10, ge=1, le=100, description="Maximum records to return")


# Generic paginated response
T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response wrapper.
    
    Usage:
        PaginatedResponse[UserRead](items=users, total=100, skip=0, limit=10)
    """
    
    items: list[T]
    total: int = Field(..., description="Total number of items")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum items per page")
    
    @property
    def has_next(self) -> bool:
        """Check if there are more pages."""
        return self.skip + self.limit < self.total


# Standard response wrappers
class MessageResponse(BaseModel):
    """Simple message response."""
    message: str


class ErrorDetail(BaseModel):
    """Error detail structure."""
    field: str | None = None
    message: str
    type: str | None = None


class ErrorResponse(BaseModel):
    """Standardized error response."""
    detail: str | list[ErrorDetail]