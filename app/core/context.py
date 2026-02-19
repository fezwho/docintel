"""
Request context using contextvars.

Provides thread-safe context storage for:
- Request ID
- User ID
- Tenant ID
- Trace ID
"""

import contextvars
from typing import Any

# Context variables
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
user_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "user_id", default=None
)
tenant_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tenant_id", default=None
)
trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)


def set_request_context(
    request_id: str | None = None,
    user_id: str | None = None,
    tenant_id: str | None = None,
    trace_id: str | None = None,
) -> None:
    """Set request context variables."""
    if request_id:
        request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)
    if tenant_id:
        tenant_id_var.set(tenant_id)
    if trace_id:
        trace_id_var.set(trace_id)


def get_request_context() -> dict[str, Any]:
    """Get all request context as a dictionary."""
    return {
        "request_id": request_id_var.get(),
        "user_id": user_id_var.get(),
        "tenant_id": tenant_id_var.get(),
        "trace_id": trace_id_var.get(),
    }


def clear_request_context() -> None:
    """Clear all context variables."""
    request_id_var.set(None)
    user_id_var.set(None)
    tenant_id_var.set(None)
    trace_id_var.set(None)