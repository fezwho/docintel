"""
Celery application configuration.

Celery handles:
- Asynchronous task execution
- Task scheduling
- Retry logic
- Distributed task processing
"""

import logging

from celery import Celery
from celery.signals import task_failure, task_success

from app.config import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "docintel",
    broker=str(settings.redis_url),
    backend=str(settings.redis_url),
    include=[
        "app.features.documents.tasks",  # Import task modules
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task execution
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task routing
    task_routes={
        "app.features.documents.tasks.process_document": {"queue": "documents"},
        "app.features.documents.tasks.extract_text": {"queue": "processing"},
        "app.features.documents.tasks.*": {"queue": "default"},
    },
    
    # Result backend
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={
        "master_name": "mymaster",
    },
    
    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completes (safer)
    task_reject_on_worker_lost=True,  # Requeue if worker dies
    task_time_limit=300,  # Hard time limit: 5 minutes
    task_soft_time_limit=240,  # Soft time limit: 4 minutes (warning)
    
    # Worker settings
    worker_prefetch_multiplier=4,  # Number of tasks to prefetch
    worker_max_tasks_per_child=1000,  # Restart worker after N tasks (memory management)
    
    # Retry settings
    task_default_max_retries=3,
    task_default_retry_delay=60,  # 1 minute between retries
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)


# Task event handlers
@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """Log successful task completion."""
    logger.info(f"Task succeeded: {sender.name}")


@task_failure.connect
def task_failure_handler(sender=None, exception=None, **kwargs):
    """Log task failures."""
    logger.error(f"Task failed: {sender.name} - {exception}")


# Celery beat schedule (periodic tasks)
celery_app.conf.beat_schedule = {
    "cleanup-failed-tasks": {
        "task": "app.features.documents.tasks.cleanup_failed_documents",
        "schedule": 3600.0,  # Every hour
    },
    "generate-daily-stats": {
        "task": "app.features.documents.tasks.generate_daily_stats",
        "schedule": 86400.0,  # Every 24 hours
    },
}