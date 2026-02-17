"""
Query optimization helpers.

Provides utilities to prevent N+1 queries and optimize
common query patterns in a multi-tenant system.
"""

import logging
from typing import Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.base import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def with_eager_loading(query, *relationships):
    """
    Add eager loading to prevent N+1 queries.
    
    Bad (N+1):
        users = await db.execute(select(User))
        for user in users:
            print(user.tenant.name)  # 1 query per user!
    
    Good (2 queries total):
        query = with_eager_loading(select(User), User.tenant)
        users = await db.execute(query)
    
    Usage:
        query = with_eager_loading(
            select(User),
            User.tenant,
            User.roles,
        )
    """
    for relationship in relationships:
        query = query.options(selectinload(relationship))
    
    return query


def with_joined_loading(query, *relationships):
    """
    Add joined loading for single relationships.
    
    Use when you always need the related data and
    want a single SQL JOIN instead of separate queries.
    
    Note: selectinload is usually better for collections,
    joinedload for single relationships.
    """
    for relationship in relationships:
        query = query.options(joinedload(relationship))
    
    return query


class QueryBuilder:
    """
    Fluent query builder with optimization helpers.
    
    Usage:
        results, total = await (
            QueryBuilder(db, Document)
            .filter(Document.tenant_id == tenant_id)
            .filter(Document.status == "completed")
            .eager_load(Document.uploaded_by)
            .order_by(Document.created_at, "desc")
            .paginate(skip=0, limit=10)
            .execute()
        )
    """
    
    def __init__(self, db: AsyncSession, model: Type[T]):
        self.db = db
        self.model = model
        self._query = select(model)
        self._count_query = None
        self._skip = 0
        self._limit = 10
        self._eager_loads = []
    
    def filter(self, *conditions):
        """Add WHERE conditions."""
        self._query = self._query.where(*conditions)
        return self
    
    def eager_load(self, *relationships):
        """Add eager loading for relationships."""
        for rel in relationships:
            self._query = self._query.options(selectinload(rel))
        return self
    
    def order_by(self, column, direction: str = "desc"):
        """Add ORDER BY clause."""
        if direction == "desc":
            self._query = self._query.order_by(column.desc())
        else:
            self._query = self._query.order_by(column.asc())
        return self
    
    def paginate(self, skip: int = 0, limit: int = 10):
        """Add pagination."""
        self._skip = skip
        self._limit = limit
        return self
    
    async def execute(self) -> tuple[list[T], int]:
        """
        Execute query and return results with total count.
        
        Runs two queries:
        1. Count query (for pagination metadata)
        2. Data query (with pagination applied)
        
        Returns:
            Tuple of (items, total_count)
        """
        from sqlalchemy import func
        
        # Count query (without pagination)
        count_query = select(func.count()).select_from(
            self._query.subquery()
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Data query (with pagination)
        data_query = self._query.offset(self._skip).limit(self._limit)
        result = await self.db.execute(data_query)
        items = list(result.scalars().all())
        
        logger.debug(
            f"QueryBuilder executed: {self.model.__name__} "
            f"({len(items)}/{total} results)"
        )
        
        return items, total
    
    async def execute_cursor(
        self,
        cursor_field,
        cursor: str | None = None,
        limit: int = 10,
    ) -> tuple[list[T], str | None, str | None]:
        """
        Execute query with cursor-based pagination.
        
        More efficient than offset pagination for large datasets.
        
        Returns:
            Tuple of (items, next_cursor, prev_cursor)
        """
        from app.schemas.pagination import decode_cursor, encode_cursor
        
        query = self._query
        
        if cursor:
            try:
                cursor_data = decode_cursor(cursor)
                last_value = cursor_data.get("last_value")
                direction = cursor_data.get("direction", "next")
                
                if direction == "next":
                    query = query.where(cursor_field < last_value)
                else:
                    query = query.where(cursor_field > last_value)
            except ValueError:
                pass  # Invalid cursor, start from beginning
        
        # Fetch one extra to know if there's a next page
        query = query.order_by(cursor_field.desc()).limit(limit + 1)
        result = await self.db.execute(query)
        items = list(result.scalars().all())
        
        # Determine if there's a next page
        has_next = len(items) > limit
        if has_next:
            items = items[:limit]  # Remove the extra item
        
        # Build cursors
        next_cursor = None
        prev_cursor = None
        
        if has_next and items:
            last_item = items[-1]
            next_cursor = encode_cursor({
                "last_value": str(getattr(last_item, cursor_field.key)),
                "last_id": last_item.id,
                "direction": "next",
            })
        
        if cursor and items:
            first_item = items[0]
            prev_cursor = encode_cursor({
                "last_value": str(getattr(first_item, cursor_field.key)),
                "last_id": first_item.id,
                "direction": "prev",
            })
        
        return items, next_cursor, prev_cursor