"""
Tenant isolation utilities.
"""

import logging
from typing import Type, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import forbidden, not_found
from app.models.base import BaseModel
from app.models.user import User

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def get_tenant_scoped_query(
    model: Type[T],
    user: User,
) -> Select:
    """
    Create a query automatically scoped to user's tenant.
    
    Usage:
        query = get_tenant_scoped_query(Document, current_user)
        result = await db.execute(query.where(Document.status == "published"))
    
    Args:
        model: SQLAlchemy model class
        user: Current user (provides tenant_id)
        
    Returns:
        SQLAlchemy select statement scoped to tenant
    """
    # Superusers can see all tenants (for admin operations)
    if user.is_superuser:
        return select(model)
    
    # Check if model has tenant_id column
    if not hasattr(model, "tenant_id"):
        logger.warning(f"Model {model.__name__} does not have tenant_id column")
        return select(model)
    
    # Scope to user's tenant
    return select(model).where(model.tenant_id == user.tenant_id)


async def verify_tenant_access(
    db: AsyncSession,
    model: Type[T],
    resource_id: str,
    user: User,
) -> T:
    """
    Fetch a resource and verify tenant access.
    
    Usage:
        document = await verify_tenant_access(db, Document, doc_id, current_user)
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        resource_id: ID of the resource to fetch
        user: Current user
        
    Returns:
        The resource if access is allowed
        
    Raises:
        HTTPException: 404 if not found, 403 if wrong tenant
    """
    # Fetch resource
    result = await db.execute(
        select(model).where(model.id == resource_id)
    )
    resource = result.scalar_one_or_none()
    
    if not resource:
        raise not_found(f"{model.__name__} not found")
    
    # Superusers bypass tenant check
    if user.is_superuser:
        return resource
    
    # Verify tenant access
    if hasattr(resource, "tenant_id") and resource.tenant_id != user.tenant_id:
        logger.warning(
            f"Tenant access violation: User {user.id} (tenant {user.tenant_id}) "
            f"tried to access {model.__name__} {resource_id} (tenant {resource.tenant_id})"
        )
        raise forbidden("Access denied to this resource")
    
    return resource


class TenantScope:
    """
    Context manager for tenant-scoped operations.
    
    Usage:
        async with TenantScope(db, current_user) as scoped_db:
            # All queries automatically scoped to tenant
            documents = await scoped_db.execute(select(Document))
    """
    
    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user
    
    async def __aenter__(self):
        # Store tenant context
        self.db.info["tenant_id"] = self.user.tenant_id
        self.db.info["user_id"] = self.user.id
        return self.db
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Clear tenant context
        self.db.info.pop("tenant_id", None)
        self.db.info.pop("user_id", None)