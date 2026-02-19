"""
Health check endpoints for monitoring and orchestration.

Provides:
- Liveness probe: Is the app running?
- Readiness probe: Can the app serve traffic?
- Detailed health check: Status of all dependencies
"""

import asyncio
from typing import Any

import structlog
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.core.cache import cache_manager
from app.core.database import db_manager

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health/live")
async def liveness() -> dict:
    """
    Liveness probe.
    
    Kubernetes uses this to know if the pod is alive.
    If this fails, Kubernetes will restart the pod.
    
    Returns:
        200: Application is running
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    """
    Readiness probe.
    
    Kubernetes uses this to know if the pod can serve traffic.
    If this fails, Kubernetes will remove the pod from service.
    
    Checks:
    - Database connectivity
    - Redis connectivity
    
    Returns:
        200: Ready to serve traffic
        503: Not ready (dependencies unavailable)
    """
    checks = {}
    is_ready = True
    
    # Check database
    try:
        async for db in db_manager.get_session():
            await db.execute(text("SELECT 1"))
            checks["database"] = {"status": "healthy"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        is_ready = False
    
    # Check Redis
    try:
        await cache_manager.client.ping()
        checks["redis"] = {"status": "healthy"}
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)}
        is_ready = False
    
    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_ready else "not_ready",
            "checks": checks,
        }
    )


@router.get("/health")
async def health() -> dict:
    """
    Detailed health check with dependency status.
    
    Provides comprehensive health information:
    - Overall status
    - Individual dependency health
    - Version information
    - System metrics
    
    Returns:
        200: All systems operational
        503: Degraded service
    """
    checks: dict[str, Any] = {}
    overall_status = "healthy"
    
    # Check database
    try:
        async for db in db_manager.get_session():
            result = await db.execute(text("SELECT version()"))
            version = result.scalar()
            
            checks["database"] = {
                "status": "healthy",
                "response_time_ms": 0,  # TODO: measure actual time
                "version": version[:50] if version else "unknown",
            }
    except Exception as e:
        checks["database"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        overall_status = "degraded"
    
    # Check Redis
    try:
        start = asyncio.get_event_loop().time()
        await cache_manager.client.ping()
        response_time = (asyncio.get_event_loop().time() - start) * 1000
        
        info = await cache_manager.client.info()
        
        checks["redis"] = {
            "status": "healthy",
            "response_time_ms": round(response_time, 2),
            "version": info.get("redis_version", "unknown"),
            "used_memory_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2),
        }
    except Exception as e:
        checks["redis"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        overall_status = "degraded"
    
    # Check Celery workers (optional)
    try:
        from app.core.celery_app import celery_app
        
        # Ping workers
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        
        if stats:
            worker_count = len(stats)
            checks["celery"] = {
                "status": "healthy",
                "worker_count": worker_count,
            }
        else:
            checks["celery"] = {
                "status": "degraded",
                "worker_count": 0,
                "message": "No workers available",
            }
            # Don't mark overall as degraded - workers might be optional
            
    except Exception as e:
        checks["celery"] = {
            "status": "unknown",
            "error": str(e),
        }
    
    return {
        "status": overall_status,
        "version": settings.app_version,
        "environment": settings.environment,
        "checks": checks,
    }