"""
Custom exception hierarchy for the application.
"""

from typing import Any

from fastapi import HTTPException, status


class DocIntelException(Exception):
    """Base exception for all application exceptions."""
    
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(DocIntelException):
    """Raised when authentication fails."""
    pass


class AuthorizationError(DocIntelException):
    """Raised when user lacks permissions."""
    pass


class TenantAccessError(DocIntelException):
    """Raised when user tries to access another tenant's data."""
    pass


class ResourceNotFoundError(DocIntelException):
    """Raised when a requested resource doesn't exist."""
    pass


class QuotaExceededError(DocIntelException):
    """Raised when tenant exceeds resource quota."""
    pass


class ValidationError(DocIntelException):
    """Raised when input validation fails."""
    pass


# HTTP Exception helpers
def unauthorized(detail: str = "Not authenticated") -> HTTPException:
    """Return 401 Unauthorized exception."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden(detail: str = "Insufficient permissions") -> HTTPException:
    """Return 403 Forbidden exception."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )


def not_found(detail: str = "Resource not found") -> HTTPException:
    """Return 404 Not Found exception."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail,
    )


def bad_request(detail: str = "Bad request") -> HTTPException:
    """Return 400 Bad Request exception."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
    )


def conflict(detail: str = "Resource already exists") -> HTTPException:
    """Return 409 Conflict exception."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
    )