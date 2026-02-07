"""
Tenant management endpoints.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.tenant import Tenant
from app.schemas.tenant import TenantRead

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/tenants",
    tags=["Tenants"],
)


@router.get("/", response_model=List[TenantRead])
async def list_tenants(
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """
    List all tenants with pagination.
    """
    logger.info("Fetching tenants")

    result = await db.execute(
        select(Tenant)
        .offset(skip)
        .limit(limit)
        .order_by(Tenant.created_at.desc())
    )

    tenants = result.scalars().all()
    return tenants


@router.get("/{tenant_id}", response_model=TenantRead)
async def get_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get tenant by ID.
    """
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )

    tenant = result.scalar_one_or_none()

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found",
        )

    return tenant