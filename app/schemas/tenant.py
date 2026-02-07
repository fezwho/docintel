"""
Pydantic schemas for Tenant.
"""

from datetime import datetime
from pydantic import BaseModel


class TenantRead(BaseModel):
    id: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True  # Required for SQLAlchemy ORM objects