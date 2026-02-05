"""
FastAPI application factory.

This is the entry point. Application is created with proper lifecycle management,
middleware, exception handlers, and routers.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.logging import setup_logging

# Setup logging first
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan events.
    
    Startup:
    - Initialize database connections
    - Setup Redis connection pool
    - Run health checks
    
    Shutdown:
    - Close database connections
    - Cleanup resources
    """
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    
    # TODO: Initialize database connection pool (Milestone 2)
    # TODO: Initialize Redis connection pool (Milestone 7)
    
    yield  # Application is running
    
    # Cleanup
    logger.info("Shutting down application...")
    # TODO: Close database connections
    # TODO: Close Redis connections


def create_application() -> FastAPI:
    """
    Application factory.
    
    Creates and configures FastAPI application with all middleware,
    exception handlers, and routers.
    """
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Multi-tenant document intelligence platform",
        docs_url="/docs" if settings.is_development else None,  # Disable in prod
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )
    
    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Exception Handlers
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, 
        exc: RequestValidationError
    ) -> JSONResponse:
        """Handle Pydantic validation errors with clean format."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": exc.errors(),
                "body": exc.body,
            },
        )
    
    # Health Check Endpoint
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """
        Health check endpoint for load balancers and monitoring.
        
        Returns:
            200: Service is healthy
            503: Service is degraded (add DB/Redis checks later)
        """
        return {
            "status": "healthy",
            "environment": settings.environment,
            "version": settings.app_version,
        }
    
    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root() -> dict:
        """API root with basic info."""
        return {
            "message": f"Welcome to {settings.app_name}",
            "version": settings.app_version,
            "docs": "/docs" if settings.is_development else "Documentation disabled in production",
        }
    
    # TODO: Register API routers (Milestone 3+)
    # app.include_router(auth_router, prefix="/api/v1")
    
    logger.info("Application created successfully")
    return app


# Create application instance
app = create_application()


if __name__ == "__main__":
    """
    Development server entry point.
    
    In production, use: uvicorn app.main:app --host 0.0.0.0 --port 8000
    """
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload and settings.is_development,
        log_level=settings.log_level.lower(),
    )