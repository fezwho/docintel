"""
Unit tests for security utilities.

Tests password hashing, JWT generation, and token validation.
"""

import pytest
from datetime import datetime, timedelta

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


@pytest.mark.unit
class TestPasswordHashing:
    """Test password hashing and verification."""
    
    def test_hash_password(self):
        """Test password hashing."""
        password = "TestPassword123!"
        hashed = hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 50  # Bcrypt hashes are long
        assert hashed.startswith("$2b$")  # Bcrypt prefix
    
    def test_verify_password_success(self):
        """Test password verification with correct password."""
        password = "TestPassword123!"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_failure(self):
        """Test password verification with incorrect password."""
        password = "TestPassword123!"
        wrong_password = "WrongPassword123!"
        hashed = hash_password(password)
        
        assert verify_password(wrong_password, hashed) is False
    
    def test_different_hashes_for_same_password(self):
        """Test that hashing same password twice produces different hashes (salt)."""
        password = "TestPassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


@pytest.mark.unit
class TestJWTTokens:
    """Test JWT token generation and validation."""
    
    def test_create_access_token(self):
        """Test access token creation."""
        user_id = "test-user-123"
        token = create_access_token(subject=user_id)
        
        assert isinstance(token, str)
        assert len(token) > 50  # JWTs are long
        
        # Decode and verify
        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "access"
    
    def test_create_refresh_token(self):
        """Test refresh token creation."""
        user_id = "test-user-123"
        token = create_refresh_token(subject=user_id)
        
        assert isinstance(token, str)
        
        # Decode and verify
        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"
    
    def test_token_with_custom_claims(self):
        """Test token with custom claims dictionary."""
        claims = {
            "sub": "user-123",
            "email": "test@example.com",
            "tenant_id": "tenant-456",
        }
        
        token = create_access_token(subject=claims)
        payload = decode_token(token)
        
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"
        assert payload["tenant_id"] == "tenant-456"
    
    def test_token_expiration(self):
        """Test token has expiration timestamp."""
        token = create_access_token(subject="user-123")
        payload = decode_token(token)
        
        assert "exp" in payload
        assert "iat" in payload
        
        # Verify expiration is in the future
        exp_time = datetime.fromtimestamp(payload["exp"])
        assert exp_time > datetime.utcnow()
    
    def test_decode_invalid_token(self):
        """Test decoding invalid token raises error."""
        from jose import JWTError
        
        invalid_token = "invalid.token.here"
        
        with pytest.raises(JWTError):
            decode_token(invalid_token)
    
    def test_custom_expiration(self):
        """Test token with custom expiration time."""
        token = create_access_token(
            subject="user-123",
            expires_delta=timedelta(minutes=5),
        )
        
        payload = decode_token(token)
        exp_time = datetime.fromtimestamp(payload["exp"])
        iat_time = datetime.fromtimestamp(payload["iat"])
        
        # Should expire in ~5 minutes
        duration = exp_time - iat_time
        assert 4 <= duration.total_seconds() / 60 <= 6