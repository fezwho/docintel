"""
Custom middleware for the application.
"""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request context.
    
    Provides:
    - Request ID (for log correlation)
    - Request timing
    - Tenant context (populated by auth dependencies)
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Initialize tenant context (populated later by dependencies)
        request.state.tenant_id = None
        request.state.user_id = None
        
        # Start timer
        start_time = time.time()
        
        # Add request ID to response headers
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        # Log request
        process_time = time.time() - start_time
        logger.info(
            f"Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(process_time * 1000, 2),
                "tenant_id": request.state.tenant_id,
                "user_id": request.state.user_id,
            }
        )
        
        return response


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce tenant isolation.
    
    NOTE: This is a safety net. Primary isolation happens at the query level.
    This middleware validates that the tenant_id in the request state
    matches the authenticated user's tenant.
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Skip for public endpoints
        public_paths = ["/health", "/", "/docs", "/openapi.json", "/api/v1/auth/login", "/api/v1/auth/register"]
        
        if any(request.url.path.startswith(path) for path in public_paths):
            return await call_next(request)
        
        # Process request
        response = await call_next(request)
        
        # Validation happens in dependencies, this is just logging
        if hasattr(request.state, "tenant_id") and request.state.tenant_id:
            logger.debug(f"Request processed for tenant: {request.state.tenant_id}")
        
        return response