"""
Authentication dependencies for dependency injection.
"""

import logging
import secrets
from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import forbidden, unauthorized
from app.core.security import decode_token, verify_password
from app.models.api_key import APIKey
from app.models.user import User

logger = logging.getLogger(__name__)

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Get current authenticated user (JWT or API Key).
    
    Supports two authentication methods:
    1. JWT Bearer token (Authorization: Bearer <token>)
    2. API Key (Authorization: Bearer dci_...)
    
    Priority: JWT first, then API Key
    """
    if not credentials:
        raise unauthorized("Authentication required")
    
    token = credentials.credentials
    
    # Check if it's an API key (starts with "dci_")
    if token.startswith("dci_"):
        return await _authenticate_with_api_key(db, token, request)
    
    # Otherwise, treat as JWT
    return await _authenticate_with_jwt(db, token, request)


async def _authenticate_with_jwt(
    db: AsyncSession,
    token: str,
    request: Request,
) -> User:
    """Authenticate using JWT token."""
    try:
        payload = decode_token(token)
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        raise unauthorized("Invalid or expired token")
    
    # Validate token type
    token_type = payload.get("type")
    if token_type != "access":
        raise unauthorized("Invalid token type. Use access token.")
    
    # Extract user ID
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise unauthorized("Invalid token payload")
    
    # Fetch user
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        logger.warning(f"Token valid but user not found: {user_id}")
        raise unauthorized("User not found")
    
    if not user.is_active:
        raise forbidden("User account is inactive")
    
    # Set tenant context in request state
    request.state.user_id = user.id
    request.state.tenant_id = user.tenant_id
    
    return user


async def _authenticate_with_api_key(
    db: AsyncSession,
    api_key: str,
    request: Request,
) -> User:
    """
    Authenticate using API key.
    
    API Key format: dci_<random_string>
    We hash the full key and store it, only keeping prefix for identification.
    """
    # Extract prefix (first 12 chars: "dci_" + 8 chars)
    if len(api_key) < 32:
        raise unauthorized("Invalid API key format")
    
    key_prefix = api_key[:12]
    
    # Find API key by prefix
    result = await db.execute(
        select(APIKey).where(APIKey.key_prefix == key_prefix)
    )
    stored_key = result.scalar_one_or_none()
    
    if not stored_key:
        logger.warning(f"API key not found: {key_prefix}")
        raise unauthorized("Invalid API key")
    
    # Verify full key hash
    if not verify_password(api_key, stored_key.key_hash):
        logger.warning(f"API key verification failed: {key_prefix}")
        raise unauthorized("Invalid API key")
    
    # Check if key is active
    if not stored_key.is_active:
        raise forbidden("API key is inactive")
    
    # Check expiration
    if stored_key.is_expired():
        raise forbidden("API key has expired")
    
    # Update last used timestamp
    stored_key.last_used_at = datetime.utcnow()
    await db.commit()
    
    # Get associated user (API keys are owned by tenants, not users)
    # For API key auth, we'll create a virtual "service user" concept
    # For now, use the creator
    result = await db.execute(
        select(User).where(User.id == stored_key.created_by_user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise unauthorized("API key owner not found")
    
    # Set tenant context
    request.state.user_id = user.id
    request.state.tenant_id = stored_key.tenant_id
    request.state.auth_method = "api_key"
    
    logger.info(f"API key authenticated: {key_prefix}")
    
    return user


async def get_current_active_superuser(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require superuser privileges."""
    if not current_user.is_superuser:
        raise forbidden("Superuser access required")
    return current_user


def require_permission(permission_name: str):
    """
    Dependency factory for permission-based access control.
    
    Usage:
        @router.delete("/documents/{doc_id}")
        async def delete_document(
            doc_id: str,
            user: User = Depends(require_permission("documents:delete"))
        ):
            ...
    """
    async def permission_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if not current_user.has_permission(permission_name):
            raise forbidden(f"Permission required: {permission_name}")
        return current_user
    
    return permission_checker


def require_role(role_name: str):
    """
    Dependency factory for role-based access control.
    
    Usage:
        @router.get("/admin/stats")
        async def admin_stats(
            user: User = Depends(require_role("admin"))
        ):
            ...
    """
    async def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if not current_user.has_role(role_name):
            raise forbidden(f"Role required: {role_name}")
        return current_user
    
    return role_checker


# Type aliases for cleaner code
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentSuperuser = Annotated[User, Depends(get_current_active_superuser)]