"""
Redis cache layer for response caching and rate limiting.

Provides:
- Generic get/set/delete cache operations
- TTL management
- Cache key namespacing
- Serialization helpers
"""

import json
import logging
from functools import wraps
from typing import Any, Callable

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Redis-based cache manager.
    
    Handles:
    - Connection lifecycle
    - Serialization/deserialization
    - Key namespacing
    - TTL management
    """
    
    def __init__(self) -> None:
        self._client: aioredis.Redis | None = None
    
    async def init(self) -> None:
        """Initialize Redis connection pool."""
        logger.info("Initializing Redis connection...")
        
        self._client = aioredis.from_url(
            str(settings.redis_url),
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
        
        # Test connection
        await self._client.ping()
        logger.info("Redis connection initialized")
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.aclose()
            logger.info("Redis connection closed")
    
    @property
    def client(self) -> aioredis.Redis:
        """Get Redis client."""
        if not self._client:
            raise RuntimeError("Cache not initialized. Call init() first.")
        return self._client
    
    def _build_key(self, namespace: str, key: str) -> str:
        """
        Build namespaced cache key.
        
        Format: docintel:{namespace}:{key}
        Example: docintel:documents:tenant_abc:doc_list
        """
        return f"docintel:{namespace}:{key}"
    
    async def get(self, namespace: str, key: str) -> Any | None:
        """
        Get value from cache.
        
        Returns:
            Deserialized value or None if not found
        """
        cache_key = self._build_key(namespace, key)
        
        try:
            value = await self.client.get(cache_key)
            
            if value is None:
                return None
            
            return json.loads(value)
            
        except Exception as e:
            logger.warning(f"Cache get error: {cache_key} - {e}")
            return None  # Fail gracefully, don't break the app
    
    async def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            namespace: Cache namespace
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (None = use default)
            
        Returns:
            True if set successfully
        """
        cache_key = self._build_key(namespace, key)
        ttl = ttl or settings.redis_cache_ttl
        
        try:
            serialized = json.dumps(value, default=str)
            await self.client.set(cache_key, serialized, ex=ttl)
            return True
            
        except Exception as e:
            logger.warning(f"Cache set error: {cache_key} - {e}")
            return False
    
    async def delete(self, namespace: str, key: str) -> bool:
        """Delete specific cache entry."""
        cache_key = self._build_key(namespace, key)
        
        try:
            result = await self.client.delete(cache_key)
            return result > 0
            
        except Exception as e:
            logger.warning(f"Cache delete error: {cache_key} - {e}")
            return False
    
    async def invalidate_namespace(self, namespace: str) -> int:
        """
        Invalidate all keys in a namespace.
        
        Used when underlying data changes and all cached
        responses for that namespace are stale.
        
        Returns:
            Number of keys deleted
        """
        pattern = self._build_key(namespace, "*")
        
        try:
            keys = await self.client.keys(pattern)
            
            if keys:
                deleted = await self.client.delete(*keys)
                logger.info(f"Invalidated {deleted} keys in namespace: {namespace}")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.warning(f"Cache invalidate error: {namespace} - {e}")
            return 0
    
    async def exists(self, namespace: str, key: str) -> bool:
        """Check if cache key exists."""
        cache_key = self._build_key(namespace, key)
        
        try:
            return bool(await self.client.exists(cache_key))
        except Exception as e:
            logger.warning(f"Cache exists error: {cache_key} - {e}")
            return False
    
    async def increment(
        self,
        namespace: str,
        key: str,
        ttl: int | None = None,
    ) -> int:
        """
        Increment a counter in cache.
        
        Used for rate limiting and hit counting.
        Creates key if it doesn't exist.
        
        Returns:
            New counter value
        """
        cache_key = self._build_key(namespace, key)
        
        try:
            pipe = self.client.pipeline()
            await pipe.incr(cache_key)
            
            if ttl:
                await pipe.expire(cache_key, ttl)
            
            results = await pipe.execute()
            return results[0]
            
        except Exception as e:
            logger.error(f"Cache increment error: {cache_key} - {e}")
            raise
    
    async def get_ttl(self, namespace: str, key: str) -> int:
        """Get remaining TTL for a key in seconds."""
        cache_key = self._build_key(namespace, key)
        
        try:
            return await self.client.ttl(cache_key)
        except Exception as e:
            logger.warning(f"Cache TTL error: {cache_key} - {e}")
            return -1


# Global instance
cache_manager = CacheManager()


def cached(
    namespace: str,
    ttl: int = 300,
    key_builder: Callable | None = None,
):
    """
    Decorator for caching async function results.
    
    Usage:
        @cached(namespace="documents", ttl=60)
        async def get_document_stats(tenant_id: str) -> dict:
            ...
    
    Args:
        namespace: Cache namespace
        ttl: Time-to-live in seconds
        key_builder: Custom function to build cache key from args
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default: use function name + args
                key_parts = [func.__name__]
                key_parts.extend(str(a) for a in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)
            
            # Try to get from cache
            cached_value = await cache_manager.get(namespace, cache_key)
            
            if cached_value is not None:
                logger.debug(f"Cache hit: {namespace}:{cache_key}")
                return cached_value
            
            # Cache miss - execute function
            logger.debug(f"Cache miss: {namespace}:{cache_key}")
            result = await func(*args, **kwargs)
            
            # Store in cache
            if result is not None:
                await cache_manager.set(namespace, cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator