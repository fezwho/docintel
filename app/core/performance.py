"""
Performance monitoring utilities.
"""

import asyncio
import time
from contextvars import ContextVar
from typing import Any, Callable

import structlog
from fastapi import Request

from app.core.metrics import (
    http_request_duration_seconds,
    http_requests_in_progress,
    http_requests_total,
)

logger = structlog.get_logger(__name__)

# Context variable for tracking nested operations
operation_stack: ContextVar[list[dict]] = ContextVar("operation_stack", default=[])


class PerformanceMonitor:
    """
    Monitor performance of operations.
    
    Tracks:
    - Duration
    - Memory usage (optional)
    - Database queries
    - Cache operations
    """
    
    def __init__(self, operation_name: str, **tags: Any):
        self.operation_name = operation_name
        self.tags = tags
        self.start_time: float | None = None
        self.end_time: float | None = None
    
    async def __aenter__(self) -> "PerformanceMonitor":
        """Start monitoring."""
        self.start_time = time.time()
        
        # Add to operation stack
        stack = operation_stack.get().copy()
        stack.append({
            "operation": self.operation_name,
            "start_time": self.start_time,
        })
        operation_stack.set(stack)
        
        logger.debug(
            "operation_started",
            operation=self.operation_name,
            **self.tags,
        )
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Stop monitoring and log results."""
        self.end_time = time.time()
        duration_ms = (self.end_time - self.start_time) * 1000
        
        # Pop from operation stack
        stack = operation_stack.get().copy()
        if stack:
            stack.pop()
            operation_stack.set(stack)
        
        # Log completion
        if exc_type is None:
            logger.info(
                "operation_completed",
                operation=self.operation_name,
                duration_ms=round(duration_ms, 2),
                **self.tags,
            )
        else:
            logger.error(
                "operation_failed",
                operation=self.operation_name,
                duration_ms=round(duration_ms, 2),
                error=str(exc_val),
                **self.tags,
            )
    
    @property
    def duration_ms(self) -> float | None:
        """Get duration in milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None


async def track_http_metrics(request: Request, call_next: Callable):
    """
    Middleware to track HTTP metrics.
    
    Records:
    - Request count by endpoint and status
    - Request duration histogram
    - Requests in progress gauge
    """
    # Extract endpoint (strip query params for cardinality)
    endpoint = request.url.path
    method = request.method
    
    # Track in-progress requests
    http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()
    
    start_time = time.time()
    
    try:
        # Process request
        response = await call_next(request)
        
        # Record metrics
        duration = time.time() - start_time
        status_code = response.status_code
        
        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration)
        
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code,
        ).inc()
        
        return response
        
    finally:
        # Decrement in-progress
        http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()


def slow_operation_warning(threshold_ms: float = 1000):
    """
    Decorator to warn about slow operations.
    
    Usage:
        @slow_operation_warning(threshold_ms=500)
        async def slow_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            
            if duration_ms > threshold_ms:
                logger.warning(
                    "slow_operation_detected",
                    function=func.__name__,
                    duration_ms=round(duration_ms, 2),
                    threshold_ms=threshold_ms,
                )
            
            return result
        return wrapper
    return decorator