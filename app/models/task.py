"""
Task model for tracking background job status.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    STARTED = "started"
    RETRY = "retry"
    SUCCESS = "success"
    FAILURE = "failure"
    REVOKED = "revoked"


class Task(BaseModel):
    """
    Task tracking model.
    
    Stores information about background tasks for status checking
    and debugging.
    """
    
    __tablename__ = "tasks"
    
    # Celery task ID
    task_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Celery task ID (UUID)"
    )
    
    # Task metadata
    task_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Task function name"
    )
    
    task_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Task category (e.g., 'document_processing')"
    )
    
    # Status
    status: Mapped[TaskStatus] = mapped_column(
        String(50),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
        comment="Current task status"
    )
    
    # Progress tracking
    progress: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Task progress percentage (0-100)"
    )
    
    # Execution details
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When task execution started"
    )
    
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When task completed"
    )
    
    # Results and errors
    result: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Task result data (JSON)"
    )
    
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if failed"
    )
    
    traceback: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Full error traceback"
    )
    
    # Retry tracking
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of retry attempts"
    )
    
    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
        comment="Maximum retry attempts"
    )
    
    # Associated resource
    resource_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Type of resource being processed (e.g., 'document')"
    )
    
    resource_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="ID of resource being processed"
    )
    
    # Tenant context
    tenant_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="Tenant ID for multi-tenancy"
    )
    
    def __repr__(self) -> str:
        return f"<Task(id={self.task_id}, name={self.task_name}, status={self.status})>"