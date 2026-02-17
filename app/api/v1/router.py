"""
API v1 router aggregator.

All v1 routes are registered here.
This pattern enables clean version management.
"""

from fastapi import APIRouter

from app.features.auth.router import router as auth_router
from app.features.tenants.router import router as tenants_router
from app.features.documents.router import router as documents_router

# V1 API router
v1_router = APIRouter(prefix="/v1")

# Register all feature routers
v1_router.include_router(auth_router)
v1_router.include_router(tenants_router)
v1_router.include_router(documents_router)