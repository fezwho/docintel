"""
Integration tests for authentication service.
"""

import pytest
from sqlalchemy import select

from app.features.auth.service import auth_service
from app.models import User
from app.schemas.user import UserCreate
from tests.factories import TenantFactory, UserFactory


@pytest.mark.integration
class TestAuthService:
    """Test authentication service business logic."""
    
    async def test_authenticate_user_success(self, db_session, test_tenant):
        """Test successful user authentication."""
        # Create user with known password
        password = "Test123!"
        user = await UserFactory.create(
            db_session,
            test_tenant,
            email="auth@test.com",
            password=password,
        )
        
        # Authenticate
        authenticated = await auth_service.authenticate_user(
            db_session,
            email="auth@test.com",
            password=password,
        )
        
        assert authenticated is not None
        assert authenticated.id == user.id
        assert authenticated.email == "auth@test.com"
    
    async def test_authenticate_user_wrong_password(self, db_session, test_tenant):
        """Test authentication with wrong password."""
        user = await UserFactory.create(
            db_session,
            test_tenant,
            email="auth@test.com",
            password="CorrectPassword123!",
        )
        
        # Try wrong password
        authenticated = await auth_service.authenticate_user(
            db_session,
            email="auth@test.com",
            password="WrongPassword123!",
        )
        
        assert authenticated is None
    
    async def test_authenticate_user_not_found(self, db_session):
        """Test authentication with non-existent user."""
        authenticated = await auth_service.authenticate_user(
            db_session,
            email="nonexistent@test.com",
            password="Password123!",
        )
        
        assert authenticated is None
    
    async def test_authenticate_inactive_user(self, db_session, test_tenant):
        """Test authentication with inactive user."""
        user = await UserFactory.create(
            db_session,
            test_tenant,
            email="inactive@test.com",
            password="Test123!",
            is_active=False,
        )
        
        authenticated = await auth_service.authenticate_user(
            db_session,
            email="inactive@test.com",
            password="Test123!",
        )
        
        assert authenticated is None
    
    async def test_create_user(self, db_session, test_tenant):
        """Test creating a new user."""
        user_data = UserCreate(
            email="newuser@test.com",
            password="NewUser123!",
            full_name="New User",
            tenant_id=test_tenant.id,
        )
        
        user = await auth_service.create_user(db_session, user_data)
        
        assert user.id is not None
        assert user.email == "newuser@test.com"
        assert user.full_name == "New User"
        assert user.tenant_id == test_tenant.id
        assert user.is_active is True
        
        # Password should be hashed
        assert user.hashed_password != "NewUser123!"
    
    async def test_create_user_duplicate_email(self, db_session, test_tenant):
        """Test creating user with duplicate email fails."""
        from fastapi import HTTPException
        
        # Create first user
        await UserFactory.create(
            db_session,
            test_tenant,
            email="duplicate@test.com",
        )
        
        # Try to create another with same email
        user_data = UserCreate(
            email="duplicate@test.com",
            password="Test123!",
            tenant_id=test_tenant.id,
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.create_user(db_session, user_data)
        
        assert exc_info.value.status_code == 400
        assert "already registered" in str(exc_info.value.detail).lower()
    
    async def test_generate_tokens(self, test_user):
        """Test token generation."""
        tokens = auth_service.generate_tokens(test_user.id)
        
        assert tokens.access_token is not None
        assert tokens.refresh_token is not None
        assert tokens.token_type == "bearer"
        assert tokens.expires_in > 0