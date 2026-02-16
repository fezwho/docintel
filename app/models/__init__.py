"""
Database models package.
"""

from app.core.database import Base
from app.models.base import BaseModel
from app.models.tenant import Tenant
from app.models.user import User
from app.models.role import Permission, Role, role_permissions, user_roles
from app.models.api_key import APIKey
from app.models.document import Document, DocumentStatus, DocumentType  # NEW

__all__ = [
    "Base",
    "BaseModel",
    "Tenant",
    "User",
    "Permission",
    "Role",
    "role_permissions",
    "user_roles",
    "APIKey",
    "Document",
    "DocumentStatus",
    "DocumentType",
]