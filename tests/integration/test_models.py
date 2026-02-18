"""
Integration tests for database models.

Tests ORM behavior, relationships, and database constraints.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Document, Tenant, User
from tests.factories import DocumentFactory, TenantFactory, UserFactory


@pytest.mark.integration
class TestTenantModel:
    """Test Tenant model database operations."""
    
    async def test_create_tenant(self, db_session):
        """Test creating a tenant."""
        tenant = await TenantFactory.create(
            db_session,
            name="Test Company",
            slug="test-company",
        )
        
        assert tenant.id is not None
        assert tenant.name == "Test Company"
        assert tenant.slug == "test-company"
        assert tenant.is_active is True
        assert tenant.created_at is not None
    
    async def test_tenant_slug_unique(self, db_session):
        """Test tenant slug uniqueness constraint."""
        await TenantFactory.create(db_session, slug="duplicate-slug")
        
        # Attempting to create another tenant with same slug should fail
        with pytest.raises(IntegrityError):
            await TenantFactory.create(db_session, slug="duplicate-slug")
    
    async def test_tenant_cascade_delete(self, db_session):
        """Test that deleting tenant cascades to users."""
        tenant = await TenantFactory.create(db_session)
        user = await UserFactory.create(db_session, tenant)
        
        # Delete tenant
        await db_session.delete(tenant)
        await db_session.commit()
        
        # User should be deleted too
        result = await db_session.execute(
            select(User).where(User.id == user.id)
        )
        assert result.scalar_one_or_none() is None


@pytest.mark.integration
class TestUserModel:
    """Test User model database operations."""
    
    async def test_create_user(self, db_session, test_tenant):
        """Test creating a user."""
        user = await UserFactory.create(
            db_session,
            test_tenant,
            email="test@example.com",
            full_name="Test User",
        )
        
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.tenant_id == test_tenant.id
        assert user.is_active is True
    
    async def test_user_email_unique(self, db_session, test_tenant):
        """Test user email uniqueness constraint."""
        await UserFactory.create(
            db_session,
            test_tenant,
            email="duplicate@example.com",
        )
        
        # Same email should fail
        with pytest.raises(IntegrityError):
            await UserFactory.create(
                db_session,
                test_tenant,
                email="duplicate@example.com",
            )
    
    async def test_user_tenant_relationship(self, db_session):
        """Test user-tenant relationship loading."""
        tenant = await TenantFactory.create(db_session, name="Relationship Test")
        user = await UserFactory.create(db_session, tenant)
        
        # Refresh to load relationship
        await db_session.refresh(user, ["tenant"])
        
        assert user.tenant is not None
        assert user.tenant.name == "Relationship Test"


@pytest.mark.integration
class TestDocumentModel:
    """Test Document model database operations."""
    
    async def test_create_document(self, db_session, test_tenant, test_user):
        """Test creating a document."""
        doc = await DocumentFactory.create(
            db_session,
            test_tenant,
            test_user,
            title="Test Document",
        )
        
        assert doc.id is not None
        assert doc.title == "Test Document"
        assert doc.tenant_id == test_tenant.id
        assert doc.uploaded_by_user_id == test_user.id
    
    async def test_document_soft_delete(self, db_session, test_tenant, test_user):
        """Test document soft delete functionality."""
        doc = await DocumentFactory.create(
            db_session,
            test_tenant,
            test_user,
        )
        
        # Soft delete
        doc.is_deleted = True
        await db_session.commit()
        
        # Document still exists in database
        result = await db_session.execute(
            select(Document).where(Document.id == doc.id)
        )
        retrieved = result.scalar_one_or_none()
        
        assert retrieved is not None
        assert retrieved.is_deleted is True
    
    async def test_document_composite_index(self, db_session, test_tenant, test_user):
        """Test composite index on tenant_id + status."""
        # Create documents with different statuses
        from app.models.document import DocumentStatus
        
        await DocumentFactory.create_batch(
            db_session,
            test_tenant,
            test_user,
            count=5,
            status=DocumentStatus.COMPLETED,
        )
        
        await DocumentFactory.create_batch(
            db_session,
            test_tenant,
            test_user,
            count=3,
            status=DocumentStatus.PENDING,
        )
        
        # Query with composite index
        result = await db_session.execute(
            select(Document).where(
                Document.tenant_id == test_tenant.id,
                Document.status == DocumentStatus.COMPLETED,
            )
        )
        
        completed_docs = result.scalars().all()
        assert len(completed_docs) == 5