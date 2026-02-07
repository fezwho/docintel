"""
Tenant model for multi-tenancy.

Each tenant represents an organization/company using the platform.
"""

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Tenant(BaseModel):
    """
    Tenant (organization) model.
    
    Provides:
    - Data isolation between organizations
    - Subscription/plan management
    - Resource quotas
    """
    
    __tablename__ = "tenants"
    
    # Basic info
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Organization name"
    )
    
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="URL-friendly identifier (e.g., 'acme-corp')"
    )
    
    # Configuration
    settings: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON settings for tenant-specific config"
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Tenant active status"
    )
    
    # Resource limits (for quota enforcement)
    max_users: Mapped[int] = mapped_column(
        Integer,
        default=10,
        nullable=False,
        comment="Maximum users allowed"
    )
    
    max_documents: Mapped[int] = mapped_column(
        Integer,
        default=1000,
        nullable=False,
        comment="Maximum documents allowed"
    )
    
    max_storage_mb: Mapped[int] = mapped_column(
        Integer,
        default=5000,  # 5GB
        nullable=False,
        comment="Maximum storage in megabytes"
    )
    
    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, name={self.name})>"