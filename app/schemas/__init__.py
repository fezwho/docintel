"""
Pydantic schemas package.
"""

from app.schemas.common import (
    BaseSchema,
    ErrorResponse,
    MessageResponse,
    PaginatedResponse,
    PaginationParams,
)
from app.schemas.tenant import TenantCreate, TenantRead, TenantUpdate
from app.schemas.user import UserCreate, UserRead, UserUpdate

__all__ = [
    # Common
    "BaseSchema",
    "MessageResponse",
    "ErrorResponse",
    "PaginationParams",
    "PaginatedResponse",
    # Tenant
    "TenantCreate",
    "TenantRead",
    "TenantUpdate",
    # User
    "UserCreate",
    "UserRead",
    "UserUpdate",
]