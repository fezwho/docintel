"""
API Key model for service-to-service authentication.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class APIKey(BaseModel):
    """
    API Key for programmatic access.
    
    Used for:
    - Service-to-service authentication
    - CI/CD pipelines
    - Third-party integrations
    """
    
    __tablename__ = "api_keys"
    
    # Key details
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Descriptive name for the key"
    )
    
    # Hashed key (we store hash, not plain text)
    key_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
        index=True,
        comment="Hashed API key (bcrypt)"
    )
    
    # Prefix for identification (first 8 chars, e.g., "dci_1234")
    key_prefix: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Key prefix for identification"
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Key active status"
    )
    
    # Expiration
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Key expiration timestamp"
    )
    
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time key was used"
    )
    
    # Ownership
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated tenant"
    )
    
    created_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who created this key"
    )
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    created_by: Mapped["User"] = relationship("User")
    
    def is_expired(self) -> bool:
        """Check if key has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def __repr__(self) -> str:
        return f"<APIKey(prefix={self.key_prefix}, name={self.name})>"