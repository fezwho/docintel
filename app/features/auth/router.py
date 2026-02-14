"""
Authentication endpoints.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.features.auth.dependencies import CurrentUser, get_current_user
from app.features.auth.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterResponse,
    TokenResponse,
)
from app.features.auth.service import auth_service
from app.schemas.common import MessageResponse
from app.schemas.user import UserCreate, UserRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RegisterResponse:
    """
    Register a new user.
    
    Requirements:
    - Valid email format
    - Strong password (8+ chars, upper, lower, digit)
    - Valid tenant_id
    """
    user = await auth_service.create_user(db, user_data)
    
    return RegisterResponse(
        user=UserRead.model_validate(user),
        message="User registered successfully. Please verify your email.",
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """
    OAuth2 compatible token login.
    
    Uses OAuth2PasswordRequestForm (username/password from form data).
    We treat 'username' as email.
    """
    user = await auth_service.authenticate_user(
        db,
        email=form_data.username,  # OAuth2 standard uses 'username'
        password=form_data.password,
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return auth_service.generate_tokens(user.id)


@router.post("/login/json", response_model=TokenResponse)
async def login_json(
    login_data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """
    Login with JSON body (alternative to form data).
    
    More convenient for modern API clients.
    """
    user = await auth_service.authenticate_user(
        db,
        email=login_data.email,
        password=login_data.password,
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    return auth_service.generate_tokens(user.id)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """
    Refresh access token using refresh token.
    
    When access token expires, use this endpoint with refresh token
    to get a new access token without re-authentication.
    """
    return await auth_service.refresh_access_token(db, refresh_data.refresh_token)


@router.get("/me", response_model=UserRead)
async def get_current_user_info(
    current_user: CurrentUser,
) -> UserRead:
    """
    Get current authenticated user's information.
    
    Requires valid access token in Authorization header.
    """
    return UserRead.model_validate(current_user)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: CurrentUser,
) -> MessageResponse:
    """
    Logout endpoint.
    
    In JWT-based auth, logout is handled client-side by deleting the token.
    This endpoint exists for API consistency and future token blacklisting.
    """
    logger.info(f"User logged out: {current_user.email}")
    return MessageResponse(message="Successfully logged out")