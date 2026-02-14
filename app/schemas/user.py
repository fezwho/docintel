"""
Pydantic schemas for User.
"""

from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import BaseSchema
from app.schemas.tenant import TenantRead


class UserBase(BaseSchema):
    """Base user schema."""
    
    email: EmailStr = Field(..., description="User email address")
    full_name: str | None = Field(None, max_length=255, description="User's full name")


class UserCreate(UserBase):
    """Schema for user registration."""
    
    password: str = Field(..., min_length=8, max_length=100, description="User password")
    tenant_id: str = Field(..., description="Tenant ID to associate user with")
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """
        Validate password strength.
        
        Requirements:
        - At least 8 characters
        - Contains uppercase and lowercase
        - Contains at least one digit
        """
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(char.islower() for char in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserUpdate(BaseSchema):
    """Schema for updating user (all optional)."""
    
    email: EmailStr | None = None
    full_name: str | None = Field(None, max_length=255)
    is_active: bool | None = None


class UserRead(UserBase):
    """Schema for reading user data."""
    
    id: str
    is_active: bool
    is_superuser: bool
    is_verified: bool
    tenant_id: str
    created_at: datetime
    updated_at: datetime


class UserReadWithTenant(UserRead):
    """User data with tenant information."""
    
    tenant: TenantRead