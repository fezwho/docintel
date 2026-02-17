"""
Advanced pagination schemas.

Two pagination strategies:
1. Offset-based: Simple, supports random page access
2. Cursor-based: Efficient for large datasets, consistent ordering
"""

import base64
import json
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import Field

from app.schemas.common import BaseSchema

T = TypeVar("T")


def encode_cursor(data: dict) -> str:
    """
    Encode cursor data to opaque string.
    
    Cursor contains:
    - last_id: ID of last seen record
    - last_value: Value of sort field for last record
    - direction: Forward or backward
    """
    json_str = json.dumps(data, default=str)
    return base64.urlsafe_b64encode(json_str.encode()).decode()


def decode_cursor(cursor: str) -> dict:
    """
    Decode cursor string to data.
    
    Raises:
        ValueError: If cursor is invalid
    """
    try:
        json_str = base64.urlsafe_b64decode(cursor.encode()).decode()
        return json.loads(json_str)
    except Exception:
        raise ValueError("Invalid cursor")


class CursorPage(BaseSchema, Generic[T]):
    """
    Cursor-based paginated response.
    
    Why cursor pagination over offset?
    - Consistent: New inserts don't cause items to be skipped/duplicated
    - Efficient: O(log n) vs O(n) for deep pages
    - Scalable: No OFFSET clause (slow on large tables)
    
    Trade-off:
    - Cannot jump to arbitrary page
    - Must paginate sequentially
    """
    
    items: list[T]
    next_cursor: str | None = Field(
        None,
        description="Cursor for next page (None if no more data)"
    )
    prev_cursor: str | None = Field(
        None,
        description="Cursor for previous page (None if first page)"
    )
    has_next: bool = Field(False, description="Whether more data exists")
    has_prev: bool = Field(False, description="Whether previous data exists")
    total: int | None = Field(
        None,
        description="Total count (optional, expensive for large datasets)"
    )


class CursorParams(BaseSchema):
    """Query parameters for cursor pagination."""
    
    cursor: str | None = Field(None, description="Pagination cursor")
    limit: int = Field(10, ge=1, le=100, description="Items per page")