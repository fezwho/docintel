"""
Structured logging configuration.

Uses Python's built-in logging with structured output.
In production, switch to JSON format for log aggregation.
"""

import logging
import sys
from typing import Any

from app.config import settings


def setup_logging() -> None:
    """
    Configure application-wide logging.
    
    - Development: Human-readable console output
    - Production: JSON format for log aggregation (ELK, CloudWatch, etc.)
    """
    
    log_level = getattr(logging, settings.log_level.upper())
    
    # Create formatter
    if settings.log_format == "json":
        # In production, use a JSON formatter library like python-json-logger
        formatter = logging.Formatter(
            '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}'
        )
    else:
        # Development: readable format
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)
    
    # Silence noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module."""
    return logging.getLogger(name)