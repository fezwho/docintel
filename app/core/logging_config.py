"""
Advanced structured logging configuration.

Provides:
- JSON formatted logs for production (ELK, CloudWatch, etc.)
- Human-readable logs for development
- Correlation IDs for request tracking
- Contextual information (user, tenant, trace)
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.config import settings


def add_app_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Add application context to log entries.
    
    Adds:
    - Environment (dev/staging/prod)
    - Service name
    - Version
    """
    event_dict["environment"] = settings.environment
    event_dict["service"] = settings.app_name
    event_dict["version"] = settings.app_version
    return event_dict


def add_request_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Add request context from contextvars.
    
    In middleware, we'll set these context variables.
    """
    from app.core.context import get_request_context
    
    context = get_request_context()
    if context:
        event_dict.update(context)
    
    return event_dict


def censor_sensitive_data(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Censor sensitive information from logs.
    
    Removes:
    - Passwords
    - API keys
    - Tokens
    - Credit card numbers
    """
    sensitive_keys = {
        "password", "token", "secret", "api_key",
        "access_token", "refresh_token", "hashed_password",
        "credit_card", "ssn"
    }
    
    for key in list(event_dict.keys()):
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            event_dict[key] = "***REDACTED***"
    
    return event_dict


def setup_logging() -> None:
    """
    Configure application-wide structured logging.
    
    Production: JSON logs to stdout (for log aggregation)
    Development: Colorized console logs (human-readable)
    """
    
    # Determine log level
    log_level = getattr(logging, settings.log_level.upper())
    
    # Shared processors for all environments
    shared_processors: list[Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.contextvars.merge_contextvars,
        add_app_context,
        add_request_context,
        censor_sensitive_data,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if settings.log_format == "json":
        # Production: JSON logs
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
        
        # Configure standard library logging
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=log_level,
        )
        
    else:
        # Development: Console logs with colors
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]
        
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=log_level,
        )
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    logger = structlog.get_logger(__name__)
    logger.info(
        "logging_configured",
        log_level=settings.log_level,
        log_format=settings.log_format,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.
    
    Usage:
        logger = get_logger(__name__)
        logger.info("user_created", user_id=user.id, email=user.email)
    """
    return structlog.get_logger(name)