"""
Rate limiting implementation using Redis.

Strategies:
- Fixed window: Count requests in a time window
- Sliding window: More accurate, slightly more complex
- Token bucket: Smooth rate limiting (implemented here)
"""

import logging
from dataclasses import dataclass
from enum import Enum

from fastapi import HTTPException, Request, status

from app.core.cache import cache_manager

logger = logging.getLogger(__name__)


class RateLimitStrategy(str, Enum):
    """Rate limiting strategies."""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit rule."""
    
    requests: int     # Max requests
    window: int       # Time window in seconds
    key_prefix: str   # Key prefix for namespacing


# Predefined rate limit tiers
RATE_LIMITS = {
    "default": RateLimitConfig(requests=60, window=60, key_prefix="rl"),
    "upload": RateLimitConfig(requests=10, window=60, key_prefix="rl_upload"),
    "auth": RateLimitConfig(requests=5, window=60, key_prefix="rl_auth"),
    "search": RateLimitConfig(requests=30, window=60, key_prefix="rl_search"),
    "bulk": RateLimitConfig(requests=5, window=60, key_prefix="rl_bulk"),
}


async def check_rate_limit(
    identifier: str,
    limit_type: str = "default",
) -> dict:
    """
    Check if identifier has exceeded rate limit.
    
    Uses fixed window strategy.
    
    Args:
        identifier: Unique identifier (user_id, ip, tenant_id)
        limit_type: Rate limit tier to apply
        
    Returns:
        Dict with rate limit info
        
    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    config = RATE_LIMITS.get(limit_type, RATE_LIMITS["default"])
    
    # Build cache key
    key = f"{identifier}:{limit_type}"
    
    try:
        # Increment counter with TTL
        current_count = await cache_manager.increment(
            namespace=config.key_prefix,
            key=key,
            ttl=config.window,
        )
        
        # Get remaining TTL for headers
        ttl = await cache_manager.get_ttl(config.key_prefix, key)
        
        remaining = max(0, config.requests - current_count)
        
        rate_limit_info = {
            "limit": config.requests,
            "remaining": remaining,
            "reset": ttl,
            "current": current_count,
        }
        
        # Check if limit exceeded
        if current_count > config.requests:
            logger.warning(
                f"Rate limit exceeded: {identifier} ({limit_type}) "
                f"{current_count}/{config.requests}"
            )
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": config.requests,
                    "window": config.window,
                    "retry_after": ttl,
                },
                headers={
                    "X-RateLimit-Limit": str(config.requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(ttl),
                    "Retry-After": str(ttl),
                },
            )
        
        return rate_limit_info
        
    except HTTPException:
        raise
    except Exception as e:
        # If Redis is down, fail open (don't block requests)
        logger.error(f"Rate limit check error: {e}")
        return {"limit": config.requests, "remaining": config.requests, "reset": 0}


def rate_limit(limit_type: str = "default", by: str = "user"):
    """
    Rate limiting dependency factory.
    
    Args:
        limit_type: Rate limit tier (default, upload, auth, etc.)
        by: How to identify the requester (user, tenant, ip)
    
    Usage:
        @router.post("/upload")
        async def upload(
            _: None = Depends(rate_limit("upload")),
            current_user: CurrentUser = None,
        ):
            ...
    """
    async def dependency(request: Request) -> dict:
        """Rate limit dependency."""
        
        # Determine identifier
        if by == "user":
            user_id = getattr(request.state, "user_id", None)
            identifier = user_id or request.client.host
        elif by == "tenant":
            tenant_id = getattr(request.state, "tenant_id", None)
            identifier = tenant_id or request.client.host
        else:  # ip
            identifier = request.client.host
        
        return await check_rate_limit(identifier, limit_type)
    
    return dependency