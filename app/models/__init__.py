"""
Database models package.

Import all models here for Alembic auto-generation to work.
"""

from app.core.database import Base
from app.models.base import BaseModel
from app.models.tenant import Tenant
from app.models.user import User

# Export all models
__all__ = [
    "Base",
    "BaseModel",
    "User",
    "Tenant",
]