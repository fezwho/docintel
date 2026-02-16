"""
Role-Based Access Control (RBAC) models.
"""

from sqlalchemy import Boolean, String, Text, ForeignKey, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.core.database import Base


# Many-to-many: User <-> Role
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


# Many-to-many: Role <-> Permission
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String(36), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(BaseModel):
    """
    Permission model for fine-grained access control.
    
    Examples:
    - documents:read
    - documents:write
    - documents:delete
    - users:manage
    - analytics:view
    """
    
    __tablename__ = "permissions"
    
    # Permission identifier (e.g., "documents:read")
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="Permission identifier (resource:action format)"
    )
    
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable permission description"
    )
    
    # Tenant-scoped (None = global system permission)
    tenant_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Tenant ID for tenant-specific permissions"
    )
    
    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=role_permissions,
        back_populates="permissions",
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return f"<Permission(name={self.name})>"


class Role(BaseModel):
    """
    Role model for grouping permissions.
    
    Built-in roles:
    - admin: Full access within tenant
    - member: Standard user access
    - viewer: Read-only access
    
    Custom roles can be created per tenant.
    """
    
    __tablename__ = "roles"
    
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Role name (e.g., 'admin', 'member')"
    )
    
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Role description"
    )
    
    # Built-in roles are system-wide, custom roles are tenant-specific
    is_system_role: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="System-defined role (cannot be modified)"
    )
    
    # Tenant-scoped (None = system role)
    tenant_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Tenant ID for custom roles"
    )
    
    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles"
    )
    
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return f"<Role(name={self.name}, tenant_id={self.tenant_id})>"