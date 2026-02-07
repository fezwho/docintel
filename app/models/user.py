"""
User model for authentication and authorization.
"""

from sqlalchemy import Boolean, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class User(BaseModel):
    """
    User account model.
    
    Relationships:
    - Belongs to one Tenant
    - Has many Documents (via tenant)
    """
    
    __tablename__ = "users"
    
    # Authentication fields
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User email address (unique)"
    )
    
    hashed_password: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Bcrypt hashed password"
    )
    
    # Profile fields
    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="User's full name"
    )
    
    # Status flags
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Account active status"
    )
    
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Superuser/admin privileges"
    )
    
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Email verification status"
    )
    
    # Multi-tenancy
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated tenant ID"
    )
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="users",
        lazy="selectin"  # Avoid N+1 queries
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"