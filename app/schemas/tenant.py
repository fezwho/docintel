# """
# Pydantic schemas for Tenant.
# """

# from datetime import datetime
# from pydantic import BaseModel


# class TenantRead(BaseModel):
#     id: str
#     name: str
#     created_at: datetime

#     class Config:
#         from_attributes = True  # Required for SQLAlchemy ORM objects


"""
Pydantic schemas for Tenant.
"""

from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseSchema


class TenantBase(BaseSchema):
    """Base tenant schema with common fields."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Organization name")
    slug: str = Field(..., min_length=1, max_length=100, description="URL-friendly identifier")


class TenantCreate(TenantBase):
    """Schema for creating a new tenant."""
    
    max_users: int = Field(10, ge=1, description="Maximum users allowed")
    max_documents: int = Field(1000, ge=1, description="Maximum documents allowed")
    max_storage_mb: int = Field(5000, ge=100, description="Maximum storage in MB")


class TenantUpdate(BaseSchema):
    """Schema for updating a tenant (all fields optional)."""
    
    name: str | None = Field(None, min_length=1, max_length=255)
    max_users: int | None = Field(None, ge=1)
    max_documents: int | None = Field(None, ge=1)
    max_storage_mb: int | None = Field(None, ge=100)
    is_active: bool | None = None


class TenantRead(TenantBase):
    """Schema for reading tenant data."""
    
    id: str
    is_active: bool
    max_users: int
    max_documents: int
    max_storage_mb: int
    created_at: datetime
    updated_at: datetime


class TenantReadWithStats(TenantRead):
    """Tenant with usage statistics."""
    
    user_count: int = 0
    document_count: int = 0
    storage_used_mb: float = 0.0