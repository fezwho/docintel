@echo off
poetry run celery -A app.core.celery_app worker --loglevel=info --concurrency=4 --queues=documents,processing,default --max-tasks-per-child=100

@REM #!/bin/bash
@REM # Start Celery worker for document processing

@REM celery -A app.core.celery_app worker \
@REM     --loglevel=info \
@REM     --concurrency=4 \
@REM     --queues=documents,processing,default \
@REM     --max-tasks-per-child=100

