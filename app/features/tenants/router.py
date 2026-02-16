"""
Tenant management endpoints.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import forbidden, not_found
from app.core.tenant import verify_tenant_access
from app.features.auth.dependencies import CurrentUser, CurrentSuperuser
from app.models.tenant import Tenant
from app.schemas.tenant import TenantRead, TenantUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.get("/", response_model=list[TenantRead])
async def list_tenants(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentSuperuser,  # Only superusers can list all tenants
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
) -> list[Tenant]:
    """
    List all tenants (superuser only).
    
    Regular users can only see their own tenant via GET /tenants/me
    """
    result = await db.execute(
        select(Tenant)
        .offset(skip)
        .limit(limit)
        .order_by(Tenant.created_at.desc())
    )
    
    tenants = result.scalars().all()
    return list(tenants)


@router.get("/me", response_model=TenantRead)
async def get_my_tenant(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Tenant:
    """
    Get current user's tenant information.
    
    Any authenticated user can access their own tenant.
    """
    result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise not_found("Tenant not found")
    
    return tenant


@router.get("/{tenant_id}", response_model=TenantRead)
async def get_tenant(
    tenant_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Tenant:
    """
    Get specific tenant by ID.
    
    - Superusers: Can access any tenant
    - Regular users: Can only access their own tenant
    """
    # Verify access
    tenant = await verify_tenant_access(db, Tenant, tenant_id, current_user)
    return tenant


@router.patch("/{tenant_id}", response_model=TenantRead)
async def update_tenant(
    tenant_id: str,
    tenant_update: TenantUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Tenant:
    """
    Update tenant settings.
    
    Requires admin role within the tenant or superuser.
    """
    # Verify access
    tenant = await verify_tenant_access(db, Tenant, tenant_id, current_user)
    
    # Check if user has admin role (unless superuser)
    if not current_user.is_superuser and not current_user.has_role("admin"):
        raise forbidden("Admin role required to update tenant settings")
    
    # Update fields
    update_data = tenant_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)
    
    await db.commit()
    await db.refresh(tenant)
    
    logger.info(f"Tenant {tenant_id} updated by user {current_user.id}")
    
    return tenant