"""
Prometheus metrics for monitoring.

Metrics collected:
- HTTP request duration (histogram)
- HTTP request count by status code (counter)
- Active requests (gauge)
- Database query duration (histogram)
- Cache hit/miss rate (counter)
- Background task duration (histogram)
"""

from prometheus_client import Counter, Histogram, Gauge, Info
from functools import wraps
import time


# Application info
app_info = Info("docintel_app", "DocIntel application information")
app_info.info({
    "version": "1.0.0",
    "environment": "development",
})

# HTTP metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests in progress",
    ["method", "endpoint"],
)

# Database metrics
db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
)

db_connections_active = Gauge(
    "db_connections_active",
    "Number of active database connections",
)

db_queries_total = Counter(
    "db_queries_total",
    "Total database queries",
    ["operation", "status"],
)

# Cache metrics
cache_operations_total = Counter(
    "cache_operations_total",
    "Total cache operations",
    ["operation", "hit"],
)

cache_operation_duration_seconds = Histogram(
    "cache_operation_duration_seconds",
    "Cache operation duration in seconds",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1),
)

# Background task metrics
task_duration_seconds = Histogram(
    "task_duration_seconds",
    "Background task duration in seconds",
    ["task_name", "status"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0),
)

task_queue_length = Gauge(
    "task_queue_length",
    "Number of tasks in queue",
    ["queue_name"],
)

# Business metrics
documents_uploaded_total = Counter(
    "documents_uploaded_total",
    "Total documents uploaded",
    ["tenant_id", "document_type"],
)

documents_processed_total = Counter(
    "documents_processed_total",
    "Total documents processed",
    ["tenant_id", "status"],
)

active_users_total = Gauge(
    "active_users_total",
    "Number of active users",
    ["tenant_id"],
)

# Storage metrics
storage_bytes_used = Gauge(
    "storage_bytes_used",
    "Storage space used in bytes",
    ["tenant_id"],
)


# Decorator for tracking function execution time
def track_time(metric: Histogram, labels: dict = None):
    """
    Decorator to track function execution time.
    
    Usage:
        @track_time(http_request_duration_seconds, {"method": "GET"})
        async def my_endpoint():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)
        return wrapper
    return decorator