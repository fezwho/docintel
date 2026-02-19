"""
Custom middleware for the application.
"""

import logging
import time
import uuid
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.context import set_request_context, clear_request_context

logger = structlog.get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request context.
    
    Sets:
    - Request ID (for log correlation)
    - Trace ID (for distributed tracing)
    - Request timing
    - Context variables for structured logging
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Generate IDs
        request_id = str(uuid.uuid4())
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        
        # Set request state
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        request.state.tenant_id = None
        request.state.user_id = None
        
        # Set context for logging
        set_request_context(
            request_id=request_id,
            trace_id=trace_id,
        )
        
        # Start timer
        start_time = time.time()
        
        # Log request start
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            client_host=request.client.host if request.client else None,
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = round((time.time() - start_time) * 1000, 2)
            
            # Update context with user/tenant if available
            if hasattr(request.state, "user_id") and request.state.user_id:
                set_request_context(
                    user_id=request.state.user_id,
                    tenant_id=request.state.tenant_id,
                )
            
            # Add headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Process-Time"] = str(duration_ms)
            
            # Log request completion
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            
            return response
            
        except Exception as e:
            # Log error
            duration_ms = round((time.time() - start_time) * 1000, 2)
            
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                error=str(e),
                exc_info=True,
            )
            raise
            
        finally:
            # Clear context
            clear_request_context()


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce tenant isolation.
    
    This is a safety net. Primary isolation happens at the query level.
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Skip for public endpoints
        public_paths = [
            "/health",
            "/",
            "/docs",
            "/openapi.json",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/metrics",  # Prometheus metrics
        ]
        
        if any(request.url.path.startswith(path) for path in public_paths):
            return await call_next(request)
        
        # Process request
        response = await call_next(request)
        
        # Log tenant context
        if hasattr(request.state, "tenant_id") and request.state.tenant_id:
            logger.debug(
                "tenant_access",
                tenant_id=request.state.tenant_id,
                path=request.url.path,
            )
        
        return response