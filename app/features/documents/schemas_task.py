"""
Task-related schemas.
"""

from datetime import datetime

from pydantic import Field

from app.models.task import TaskStatus
from app.schemas.common import BaseSchema


class TaskStatusResponse(BaseSchema):
    """Task status response."""
    
    task_id: str = Field(..., description="Celery task ID")
    task_name: str
    task_type: str
    status: TaskStatus
    progress: int = Field(..., ge=0, le=100, description="Progress percentage")
    started_at: datetime | None
    completed_at: datetime | None
    result: dict | None = None
    error: str | None = None
    retry_count: int
    resource_type: str | None
    resource_id: str | None