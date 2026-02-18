"""
API tests for authentication endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.api
class TestAuthEndpoints:
    """Test authentication API endpoints."""
    
    async def test_register_user(self, client: AsyncClient, test_tenant):
        """Test user registration endpoint."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@test.com",
                "password": "NewUser123!",
                "full_name": "New User",
                "tenant_id": test_tenant.id,
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["user"]["email"] == "newuser@test.com"
        assert data["user"]["full_name"] == "New User"
        assert "password" not in data["user"]
        assert "hashed_password" not in data["user"]
    
    async def test_register_weak_password(self, client: AsyncClient, test_tenant):
        """Test registration with weak password fails."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@test.com",
                "password": "weak",  # Too weak
                "tenant_id": test_tenant.id,
            },
        )
        
        assert response.status_code == 422
    
    async def test_login_success(self, client: AsyncClient, test_user):
        """Test successful login."""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "Test123!",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    async def test_login_wrong_password(self, client: AsyncClient, test_user):
        """Test login with wrong password."""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "WrongPassword123!",
            },
        )
        
        assert response.status_code == 401
    
    async def test_login_json(self, client: AsyncClient, test_user):
        """Test JSON login endpoint."""
        response = await client.post(
            "/api/v1/auth/login/json",
            json={
                "email": test_user.email,
                "password": "Test123!",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert "refresh_token" in data
    
    async def test_get_current_user(
        self,
        authenticated_client: AsyncClient,
        test_user,
    ):
        """Test getting current user info."""
        response = await authenticated_client.get("/api/v1/auth/me")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["email"] == test_user.email
        assert data["id"] == test_user.id
    
    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """Test getting user info without authentication."""
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401


@pytest.mark.api
class TestAuthRateLimiting:
    """Test rate limiting on auth endpoints."""
    
    @pytest.mark.slow
    async def test_login_rate_limit(self, client: AsyncClient):
        """Test that too many login attempts trigger rate limit."""
        # Auth endpoints limited to 5 requests/min
        for i in range(6):
            response = await client.post(
                "/api/v1/auth/login",
                data={
                    "username": "test@test.com",
                    "password": "wrong",
                },
            )
            
            if i < 5:
                # First 5 should return 401 (unauthorized)
                assert response.status_code == 401
            else:
                # 6th should be rate limited
                assert response.status_code == 429
                assert "retry_after" in response.json()["detail"]