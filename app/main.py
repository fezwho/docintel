"""
FastAPI application factory.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.cache import cache_manager
from app.core.database import db_manager
from app.core.logging_config import setup_logging, get_logger
from app.core.middleware import RequestContextMiddleware, TenantIsolationMiddleware
from app.core.performance import track_http_metrics
from app.core.error_tracking import error_tracker

# Setup logging first
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan events."""
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
    
    # Initialize services
    db_manager.init()
    await cache_manager.init()
    
    # Update Prometheus app info
    from app.core.metrics import app_info
    app_info.info({
        "version": settings.app_version,
        "environment": settings.environment,
    })
    
    logger.info("application_ready")
    
    yield
    
    # Cleanup
    logger.info("application_shutting_down")
    await db_manager.close()
    await cache_manager.close()
    logger.info("application_shutdown_complete")


def create_application() -> FastAPI:
    """Application factory."""
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Multi-tenant document intelligence platform with full observability",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )
    
    # Middleware (order matters - first added = outermost)
    
    # Performance monitoring (outermost - tracks everything)
    @app.middleware("http")
    async def performance_middleware(request: Request, call_next):
        return await track_http_metrics(request, call_next)
    
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(TenantIsolationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, 
        exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "validation_error",
            path=request.url.path,
            errors=exc.errors(),
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors(), "body": exc.body},
        )
    
    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Global exception handler with error tracking."""
        
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Log error
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=True,
        )
        
        # Track error
        error_tracker.capture_exception(
            exc,
            context={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
            }
        )
        
        # Return clean error
        if settings.is_production:
            detail = "An internal error occurred. Please contact support."
        else:
            detail = str(exc)
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": detail,
                "request_id": request_id,
            },
        )
    
    # Register routers
    from app.api.v1.router import v1_router
    from app.api.v2.router import v2_router
    from app.api.health_router import router as health_router
    from app.api.metrics_router import router as metrics_router
    
    # Health endpoints (no prefix)
    app.include_router(health_router)
    
    # Metrics endpoint
    if settings.metrics_enabled:
        app.include_router(metrics_router)
    
    # API routers
    app.include_router(v1_router, prefix="/api")
    app.include_router(v2_router, prefix="/api")
    
    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root() -> dict:
        return {
            "message": f"Welcome to {settings.app_name}",
            "version": settings.app_version,
            "environment": settings.environment,
            "docs": "/docs" if settings.is_development else "Disabled in production",
            "health": "/health",
            "metrics": "/metrics" if settings.metrics_enabled else "Disabled",
        }
    
    logger.info("application_configured")
    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload and settings.is_development,
        log_level=settings.log_level.lower(),
        access_log=False,  # We handle logging ourselves
    )