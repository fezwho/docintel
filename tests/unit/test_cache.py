"""
Unit tests for cache layer.
"""

import pytest

from app.core.cache import CacheManager


@pytest.mark.unit
class TestCacheManager:
    """Test cache manager functionality."""
    
    def test_build_key(self):
        """Test cache key construction."""
        manager = CacheManager()
        
        key = manager._build_key("documents", "tenant_123:list")
        assert key == "docintel:documents:tenant_123:list"
    
    def test_build_key_with_colon(self):
        """Test cache key with existing colons."""
        manager = CacheManager()
        
        key = manager._build_key("users", "email:test@example.com")
        assert key == "docintel:users:email:test@example.com"