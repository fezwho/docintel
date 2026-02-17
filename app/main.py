# """
# FastAPI application factory.
# """

# import logging
# from contextlib import asynccontextmanager
# from typing import AsyncGenerator

# from fastapi import FastAPI, Request, status
# from fastapi.exceptions import RequestValidationError
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse

# from app.config import settings
# from app.core.database import db_manager
# from app.core.logging import setup_logging
# from app.core.middleware import RequestContextMiddleware, TenantIsolationMiddleware  # NEW

# # Import routers
# from app.features.auth.router import router as auth_router
# from app.features.tenants.router import router as tenants_router
# from app.features.documents.router import router as documents_router

# setup_logging()
# logger = logging.getLogger(__name__)


# @asynccontextmanager
# async def lifespan(app: FastAPI) -> AsyncGenerator:
#     """Application lifespan events."""
#     logger.info(f"Starting {settings.app_name} v{settings.app_version}")
#     logger.info(f"Environment: {settings.environment}")
    
#     db_manager.init()
    
#     yield
    
#     logger.info("Shutting down application...")
#     await db_manager.close()


# def create_application() -> FastAPI:
#     """Application factory."""
    
#     app = FastAPI(
#         title=settings.app_name,
#         version=settings.app_version,
#         description="Multi-tenant document intelligence platform",
#         docs_url="/docs" if settings.is_development else None,
#         redoc_url="/redoc" if settings.is_development else None,
#         lifespan=lifespan,
#     )
    
#     # Middleware (order matters!)
#     app.add_middleware(RequestContextMiddleware)  # NEW: Must be first
#     app.add_middleware(TenantIsolationMiddleware)  # NEW
#     app.add_middleware(
#         CORSMiddleware,
#         allow_origins=settings.cors_origins,
#         allow_credentials=True,
#         allow_methods=["*"],
#         allow_headers=["*"],
#     )
    
#     # Exception handlers
#     @app.exception_handler(RequestValidationError)
#     async def validation_exception_handler(
#         request: Request, 
#         exc: RequestValidationError
#     ) -> JSONResponse:
#         return JSONResponse(
#             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#             content={
#                 "detail": exc.errors(),
#                 "body": exc.body,
#             },
#         )
    
#     @app.get("/health", tags=["Health"])
#     async def health_check() -> dict:
#         return {
#             "status": "healthy",
#             "environment": settings.environment,
#             "version": settings.app_version,
#         }
    
#     @app.get("/", tags=["Root"])
#     async def root() -> dict:
#         return {
#             "message": f"Welcome to {settings.app_name}",
#             "version": settings.app_version,
#             "docs": "/docs" if settings.is_development else "Documentation disabled",
#         }
    
#     # Register routers
#     app.include_router(auth_router, prefix="/api/v1")
#     app.include_router(tenants_router, prefix="/api/v1")
#     app.include_router(documents_router, prefix="/api/v1")
    
#     logger.info("Application created successfully")
#     return app


# app = create_application()


# if __name__ == "__main__":
#     import uvicorn
    
#     uvicorn.run(
#         "app.main:app",
#         host=settings.host,
#         port=settings.port,
#         reload=settings.reload and settings.is_development,
#         log_level=settings.log_level.lower(),
#     )





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
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware, TenantIsolationMiddleware

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan events."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    
    # Initialize services
    db_manager.init()
    await cache_manager.init()  # NEW
    
    yield
    
    # Cleanup
    logger.info("Shutting down application...")
    await db_manager.close()
    await cache_manager.close()  # NEW


def create_application() -> FastAPI:
    """Application factory."""
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Multi-tenant document intelligence platform",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )
    
    # Middleware (order matters - first added = outermost)
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
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors(), "body": exc.body},
        )
    
    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """
        Global exception handler.
        
        Catches unhandled exceptions and returns clean error response.
        In production: also sends to error tracking (Sentry, etc.)
        """
        request_id = getattr(request.state, "request_id", "unknown")
        
        logger.error(
            f"Unhandled exception: {exc}",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
            },
            exc_info=True,
        )
        
        # Don't expose internal errors in production
        if settings.is_production:
            detail = "An internal error occurred"
        else:
            detail = str(exc)
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": detail,
                "request_id": request_id,
            },
        )
    
    # Health endpoint with dependency checks
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """
        Health check with dependency status.
        
        Checks:
        - Database connectivity
        - Redis connectivity
        """
        health = {
            "status": "healthy",
            "environment": settings.environment,
            "version": settings.app_version,
            "dependencies": {},
        }
        
        # Check database
        try:
            async for db in db_manager.get_session():
                from sqlalchemy import text
                await db.execute(text("SELECT 1"))
            health["dependencies"]["database"] = "healthy"
        except Exception as e:
            health["dependencies"]["database"] = f"unhealthy: {e}"
            health["status"] = "degraded"
        
        # Check Redis
        try:
            await cache_manager.client.ping()
            health["dependencies"]["redis"] = "healthy"
        except Exception as e:
            health["dependencies"]["redis"] = f"unhealthy: {e}"
            health["status"] = "degraded"
        
        return health
    
    @app.get("/", tags=["Root"])
    async def root() -> dict:
        return {
            "message": f"Welcome to {settings.app_name}",
            "version": settings.app_version,
            "docs": "/docs" if settings.is_development else "Disabled in production",
            "api_versions": ["v1", "v2"],
        }
    
    # Register versioned routers
    from app.api.v1.router import v1_router
    from app.api.v2.router import v2_router
    
    app.include_router(v1_router, prefix="/api")
    app.include_router(v2_router, prefix="/api")
    
    logger.info("Application created successfully")
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
    )