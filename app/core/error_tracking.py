"""
Error tracking and reporting.

In production, integrate with Sentry, Rollbar, or similar.
This module provides the interface.
"""

import sys
import traceback
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ErrorTracker:
    """
    Error tracking interface.
    
    In production, replace with actual Sentry SDK:
        import sentry_sdk
        sentry_sdk.init(dsn="your-dsn")
    """
    
    def __init__(self, enabled: bool = False, dsn: str | None = None):
        self.enabled = enabled
        self.dsn = dsn
        
        if enabled and dsn:
            self._init_sentry(dsn)
    
    def _init_sentry(self, dsn: str) -> None:
        """Initialize Sentry SDK."""
        try:
            import sentry_sdk
            from sentry_sdk.integrations.asyncio import AsyncioIntegration
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
            
            sentry_sdk.init(
                dsn=dsn,
                environment=self._get_environment(),
                traces_sample_rate=0.1,  # 10% of transactions
                profiles_sample_rate=0.1,  # 10% of transactions
                integrations=[
                    FastApiIntegration(),
                    SqlalchemyIntegration(),
                    AsyncioIntegration(),
                ],
            )
            
            logger.info("sentry_initialized")
            
        except ImportError:
            logger.warning("sentry_sdk_not_installed")
    
    def _get_environment(self) -> str:
        """Get environment name."""
        from app.config import settings
        return settings.environment
    
    def capture_exception(
        self,
        exception: Exception,
        context: dict[str, Any] | None = None,
        level: str = "error",
    ) -> str | None:
        """
        Capture and report an exception.
        
        Args:
            exception: The exception to report
            context: Additional context (user, request, etc.)
            level: Error level (error, warning, info)
            
        Returns:
            Event ID from error tracker (or None)
        """
        if not self.enabled:
            # Just log locally
            logger.error(
                "exception_captured",
                exception=str(exception),
                exception_type=type(exception).__name__,
                context=context,
                exc_info=True,
            )
            return None
        
        try:
            import sentry_sdk
            
            # Set context
            if context:
                with sentry_sdk.push_scope() as scope:
                    for key, value in context.items():
                        scope.set_context(key, value)
                    
                    event_id = sentry_sdk.capture_exception(exception)
                    return event_id
            else:
                event_id = sentry_sdk.capture_exception(exception)
                return event_id
                
        except Exception as e:
            logger.error(
                "error_tracking_failed",
                error=str(e),
                original_exception=str(exception),
            )
            return None
    
    def capture_message(
        self,
        message: str,
        level: str = "info",
        context: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Capture a message (non-exception event).
        
        Useful for:
        - Important business events
        - Performance issues
        - Security events
        """
        if not self.enabled:
            logger.info("message_captured", message=message, context=context)
            return None
        
        try:
            import sentry_sdk
            
            if context:
                with sentry_sdk.push_scope() as scope:
                    for key, value in context.items():
                        scope.set_context(key, value)
                    
                    event_id = sentry_sdk.capture_message(message, level=level)
                    return event_id
            else:
                event_id = sentry_sdk.capture_message(message, level=level)
                return event_id
                
        except Exception as e:
            logger.error("error_tracking_failed", error=str(e))
            return None


# Global error tracker instance
error_tracker = ErrorTracker(
    enabled=False,  # Set to True in production with DSN
    dsn=None,  # Set from environment variable
)