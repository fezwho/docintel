"""
Database session management with async SQLAlchemy 2.0.

Provides:
- Async engine with connection pooling
- Session factory with proper lifecycle
- Dependency injection for route handlers
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, QueuePool

from app.config import settings

logger = logging.getLogger(__name__)


# Base class for all ORM models
class Base(DeclarativeBase):
    """
    Base class for all database models.
    
    Provides:
    - Common metadata for all tables
    - Type hints for SQLAlchemy
    """
    pass


class DatabaseManager:
    """
    Manages database engine and session lifecycle.
    
    Singleton pattern ensures one engine per application.
    """
    
    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
    
    def init(self) -> None:
        """
        Initialize database engine and session factory.
        
        Called during application startup (lifespan event).
        """
        logger.info("Initializing database connection...")
        
        # Connection pool configuration
        if settings.is_development:
            # Development: more verbose logging, NullPool for simplicity
            poolclass = NullPool
            echo = settings.db_echo
        else:
            # Production: connection pooling for performance
            poolclass = QueuePool
            echo = False
        
        # Create async engine
        self._engine = create_async_engine(
            str(settings.database_url),
            echo=echo,
            poolclass=poolclass,
            # pool_size=settings.db_pool_size,
            # max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,  # Verify connections before using
        )
        
        # Session factory
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Don't expire objects after commit
            autoflush=False,  # Manual control over flushes
            autocommit=False,  # Explicit transaction management
        )
        
        logger.info("Database connection initialized successfully")
    
    async def close(self) -> None:
        """
        Close database connections.
        
        Called during application shutdown (lifespan event).
        """
        if self._engine:
            logger.info("Closing database connections...")
            await self._engine.dispose()
            logger.info("Database connections closed")
    
    @property
    def engine(self) -> AsyncEngine:
        """Get the database engine."""
        if not self._engine:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._engine
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Dependency injection for database sessions.
        
        Usage in FastAPI:
            @router.get("/users")
            async def get_users(db: AsyncSession = Depends(db_manager.get_session)):
                result = await db.execute(select(User))
                return result.scalars().all()
        
        Yields:
            AsyncSession: Database session with automatic cleanup
        """
        if not self._session_factory:
            raise RuntimeError("Database not initialized. Call init() first.")
        
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()  # Auto-commit on success
            except Exception:
                await session.rollback()  # Auto-rollback on error
                raise
            finally:
                await session.close()


# Global instance
db_manager = DatabaseManager()


# Convenience function for dependency injection
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.
    
    Usage:
        from app.core.database import get_db
        
        @router.get("/users")
        async def list_users(db: AsyncSession = Depends(get_db)):
            ...
    """
    async for session in db_manager.get_session():
        yield session