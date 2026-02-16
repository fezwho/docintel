"""
User model for authentication and authorization.
"""

from sqlalchemy import Boolean, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class User(BaseModel):
    """User account model."""
    
    __tablename__ = "users"
    
    # Authentication
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
    
    # Profile
    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="User's full name"
    )
    
    # Status
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
        lazy="selectin"
    )
    
    # NEW: Roles relationship
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin"
    )
    
    def has_permission(self, permission_name: str) -> bool:
        """
        Check if user has a specific permission.
        
        Args:
            permission_name: Permission identifier (e.g., "documents:read")
            
        Returns:
            True if user has the permission (via any role)
        """
        if self.is_superuser:
            return True
        
        for role in self.roles:
            for permission in role.permissions:
                if permission.name == permission_name:
                    return True
        
        return False
    
    def has_role(self, role_name: str) -> bool:
        """
        Check if user has a specific role.
        
        Args:
            role_name: Role name (e.g., "admin")
            
        Returns:
            True if user has the role
        """
        return any(role.name == role_name for role in self.roles)
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"