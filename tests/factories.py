"""
Factory pattern for creating test data.

Provides easy-to-use functions for creating test objects
with sensible defaults and optional overrides.
"""

from datetime import datetime
from typing import Any

from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Document, Tenant, User
from app.models.document import DocumentStatus, DocumentType

fake = Faker()


class TenantFactory:
    """Factory for creating test tenants."""
    
    @staticmethod
    async def create(
        db: AsyncSession,
        **kwargs: Any,
    ) -> Tenant:
        """
        Create a test tenant.
        
        Usage:
            tenant = await TenantFactory.create(db, name="Custom Corp")
        """
        defaults = {
            "name": fake.company(),
            "slug": fake.slug(),
            "is_active": True,
            "max_users": 50,
            "max_documents": 5000,
            "max_storage_mb": 5000,
        }
        defaults.update(kwargs)
        
        tenant = Tenant(**defaults)
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        return tenant


class UserFactory:
    """Factory for creating test users."""
    
    @staticmethod
    async def create(
        db: AsyncSession,
        tenant: Tenant,
        **kwargs: Any,
    ) -> User:
        """
        Create a test user.
        
        Usage:
            user = await UserFactory.create(db, tenant, email="custom@test.com")
        """
        password = kwargs.pop("password", "Test123!")
        
        defaults = {
            "email": fake.email(),
            "hashed_password": hash_password(password),
            "full_name": fake.name(),
            "is_active": True,
            "is_superuser": False,
            "is_verified": True,
            "tenant_id": tenant.id,
        }
        defaults.update(kwargs)
        
        user = User(**defaults)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    
    @staticmethod
    async def create_batch(
        db: AsyncSession,
        tenant: Tenant,
        count: int = 5,
        **kwargs: Any,
    ) -> list[User]:
        """Create multiple users at once."""
        users = []
        for _ in range(count):
            user = await UserFactory.create(db, tenant, **kwargs)
            users.append(user)
        return users


class DocumentFactory:
    """Factory for creating test documents."""
    
    @staticmethod
    async def create(
        db: AsyncSession,
        tenant: Tenant,
        user: User,
        **kwargs: Any,
    ) -> Document:
        """
        Create a test document.
        
        Usage:
            doc = await DocumentFactory.create(db, tenant, user, title="My Doc")
        """
        defaults = {
            "title": fake.sentence(nb_words=4),
            "description": fake.text(max_nb_chars=200),
            "filename": f"{fake.word()}.txt",
            "file_path": f"test/{fake.uuid4()}.txt",
            "file_size": fake.random_int(min=1000, max=1000000),
            "mime_type": "text/plain",
            "file_hash": fake.sha256(),
            "document_type": DocumentType.TEXT,
            "status": DocumentStatus.COMPLETED,
            "tenant_id": tenant.id,
            "uploaded_by_user_id": user.id,
        }
        defaults.update(kwargs)
        
        document = Document(**defaults)
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document
    
    @staticmethod
    async def create_batch(
        db: AsyncSession,
        tenant: Tenant,
        user: User,
        count: int = 10,
        **kwargs: Any,
    ) -> list[Document]:
        """Create multiple documents at once."""
        documents = []
        for _ in range(count):
            doc = await DocumentFactory.create(db, tenant, user, **kwargs)
            documents.append(doc)
        return documents