"""
Base model with common fields for all entities.

Provides:
- Primary key (UUID)
- Timestamps (created_at, updated_at)
- Soft delete support
- Tenant isolation field
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BaseModel(Base):
    """
    Abstract base model for all database tables.
    
    Provides common fields:
    - id: UUID primary key
    - created_at: Timestamp when record was created
    - updated_at: Timestamp when record was last modified
    
    Note: This is an abstract class (no __tablename__).
    Subclasses must define __tablename__.
    """
    
    __abstract__ = True  # Don't create a table for this class
    
    # UUID primary key (better than auto-increment for distributed systems)
    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier"
    )
    
    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when record was created"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Timestamp when record was last updated"
    )
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<{self.__class__.__name__}(id={self.id})>"
    
    def dict(self) -> dict[str, Any]:
        """
        Convert model to dictionary.
        
        Useful for serialization, but prefer Pydantic schemas in routes.
        """
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }