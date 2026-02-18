"""
Pytest fixtures for all tests.

Provides:
- Test database with automatic cleanup
- Authenticated test clients
- Mock services (Celery, storage, etc.)
- Factory fixtures for creating test data
"""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.main import create_application
from app.models import Tenant, User, Role, Permission


# Test database URL (separate from development database)
TEST_DATABASE_URL = "postgresql+asyncpg://docintel:dev_password_change_in_prod@localhost:5432/docintel_test"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """
    Create event loop for entire test session.
    
    This fixture ensures all async tests use the same event loop.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db_engine():
    """
    Create test database engine.
    
    Uses NullPool to avoid connection issues in tests.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop all tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create database session for a test.
    
    Each test gets a clean session with automatic rollback.
    This ensures test isolation.
    """
    async_session = sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        # Begin nested transaction
        await session.begin()
        
        yield session
        
        # Rollback transaction (undo all test changes)
        await session.rollback()


@pytest_asyncio.fixture
async def app(db_session: AsyncSession):
    """
    Create FastAPI test application.
    
    Overrides the database dependency to use test database.
    """
    application = create_application()
    
    # Override database dependency
    async def override_get_db():
        yield db_session
    
    application.dependency_overrides[get_db] = override_get_db
    
    return application


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """
    Create async HTTP client for testing API endpoints.
    
    Usage:
        async def test_endpoint(client):
            response = await client.get("/api/v1/documents/")
            assert response.status_code == 200
    """
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# Test data factories
@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession) -> Tenant:
    """Create a test tenant."""
    tenant = Tenant(
        name="Test Corporation",
        slug="test-corp",
        is_active=True,
        max_users=100,
        max_documents=10000,
        max_storage_mb=10000,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    """Create a test user."""
    from app.core.security import hash_password
    
    user = User(
        email="test@example.com",
        hashed_password=hash_password("Test123!"),
        full_name="Test User",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        tenant_id=test_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_superuser(db_session: AsyncSession, test_tenant: Tenant) -> User:
    """Create a test superuser."""
    from app.core.security import hash_password
    
    user = User(
        email="admin@example.com",
        hashed_password=hash_password("Admin123!"),
        full_name="Admin User",
        is_active=True,
        is_superuser=True,
        is_verified=True,
        tenant_id=test_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def test_token(test_user: User) -> str:
    """Generate JWT token for test user."""
    return create_access_token(subject=test_user.id)


@pytest.fixture
def test_superuser_token(test_superuser: User) -> str:
    """Generate JWT token for test superuser."""
    return create_access_token(subject=test_superuser.id)


@pytest_asyncio.fixture
async def authenticated_client(
    client: AsyncClient,
    test_token: str,
) -> AsyncClient:
    """HTTP client with authentication headers."""
    client.headers.update({"Authorization": f"Bearer {test_token}"})
    return client


@pytest_asyncio.fixture
async def superuser_client(
    client: AsyncClient,
    test_superuser_token: str,
) -> AsyncClient:
    """HTTP client with superuser authentication."""
    client.headers.update({"Authorization": f"Bearer {test_superuser_token}"})
    return client


# Mock external services
@pytest.fixture
def mock_celery(monkeypatch):
    """
    Mock Celery tasks to run synchronously in tests.
    
    This prevents actual background tasks from running during tests.
    """
    from app.features.documents import tasks
    
    # Mock the delay method to execute immediately
    def mock_delay(self, *args, **kwargs):
        # Instead of queueing, execute immediately
        return self.apply(args=args, kwargs=kwargs)
    
    # Patch all task delay methods
    for task_name in dir(tasks):
        task = getattr(tasks, task_name)
        if hasattr(task, 'delay'):
            monkeypatch.setattr(task, 'delay', lambda *a, **k: None)
    
    return tasks


@pytest.fixture
def mock_storage(monkeypatch, tmp_path):
    """
    Mock file storage to use temporary directory.
    
    This prevents test files from polluting the actual upload directory.
    """
    from app.features.documents.storage import LocalFileStorage
    
    # Create temp storage instance
    temp_storage = LocalFileStorage(str(tmp_path))
    
    # Mock get_storage to return temp storage
    from app.features.documents import storage
    monkeypatch.setattr(storage, 'get_storage', lambda: temp_storage)
    
    return temp_storage


@pytest.fixture
def mock_cache(monkeypatch):
    """
    Mock Redis cache with in-memory dictionary.
    
    This allows cache testing without running Redis.
    """
    cache_dict = {}
    
    class MockCacheManager:
        async def get(self, namespace, key):
            return cache_dict.get(f"{namespace}:{key}")
        
        async def set(self, namespace, key, value, ttl=None):
            cache_dict[f"{namespace}:{key}"] = value
            return True
        
        async def delete(self, namespace, key):
            cache_dict.pop(f"{namespace}:{key}", None)
            return True
        
        async def invalidate_namespace(self, namespace):
            keys_to_delete = [k for k in cache_dict if k.startswith(f"{namespace}:")]
            for key in keys_to_delete:
                del cache_dict[key]
            return len(keys_to_delete)
    
    from app.core import cache
    monkeypatch.setattr(cache, 'cache_manager', MockCacheManager())
    
    return cache_dict