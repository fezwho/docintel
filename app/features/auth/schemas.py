"""
Authentication-specific schemas.
"""

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema
from app.schemas.user import UserRead


class LoginRequest(BaseSchema):
    """Login request schema."""
    
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., description="User password")


class TokenResponse(BaseSchema):
    """Token response schema."""
    
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")


class TokenPayload(BaseSchema):
    """Decoded JWT token payload."""
    
    sub: str = Field(..., description="Subject (user ID)")
    exp: int = Field(..., description="Expiration timestamp")
    iat: int = Field(..., description="Issued at timestamp")
    type: str = Field(..., description="Token type (access/refresh)")


class RefreshTokenRequest(BaseSchema):
    """Refresh token request."""
    
    refresh_token: str = Field(..., description="Valid refresh token")


class RegisterResponse(BaseSchema):
    """User registration response."""
    
    user: UserRead
    message: str = "User registered successfully"