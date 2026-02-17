"""
API v2 router.

V2 extends V1 with:
- Cursor-based pagination (replacing offset/limit)
- Enhanced bulk operations
- Richer response envelopes
"""

from fastapi import APIRouter

# V2 imports (will use improved routers)
from app.features.documents.router_v2 import router as documents_v2_router

v2_router = APIRouter(prefix="/v2")

# Register v2 routers
v2_router.include_router(documents_v2_router)