"""
API tests for document endpoints.
"""

import io

import pytest
from httpx import AsyncClient

from tests.factories import DocumentFactory


@pytest.mark.api
class TestDocumentEndpoints:
    """Test document API endpoints."""
    
    async def test_list_documents(
        self,
        authenticated_client: AsyncClient,
        db_session,
        test_tenant,
        test_user,
    ):
        """Test listing documents."""
        # Create test documents
        await DocumentFactory.create_batch(
            db_session,
            test_tenant,
            test_user,
            count=3,
        )
        
        response = await authenticated_client.get("/api/v1/documents/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] >= 3
        assert len(data["items"]) >= 3
        assert "skip" in data
        assert "limit" in data
    
    async def test_list_documents_pagination(
        self,
        authenticated_client: AsyncClient,
        db_session,
        test_tenant,
        test_user,
    ):
        """Test document pagination."""
        # Create 15 documents
        await DocumentFactory.create_batch(
            db_session,
            test_tenant,
            test_user,
            count=15,
        )
        
        # First page
        response = await authenticated_client.get(
            "/api/v1/documents/?skip=0&limit=10"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 10
        assert data["total"] >= 15
        
        # Second page
        response = await authenticated_client.get(
            "/api/v1/documents/?skip=10&limit=10"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) >= 5
    
    async def test_upload_document(
        self,
        authenticated_client: AsyncClient,
        mock_storage,
        mock_celery,
    ):
        """Test document upload."""
        # Create fake file
        file_content = b"Test document content"
        files = {
            "file": ("test.txt", io.BytesIO(file_content), "text/plain")
        }
        data = {
            "title": "Test Document",
            "description": "A test document",
        }
        
        response = await authenticated_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
        )
        
        assert response.status_code == 201
        result = response.json()
        
        assert result["document"]["title"] == "Test Document"
        assert result["document"]["filename"] == "test.txt"
        assert "task_id" in result
    
    async def test_upload_invalid_file_type(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test uploading invalid file type."""
        files = {
            "file": ("test.exe", io.BytesIO(b"fake exe"), "application/x-msdownload")
        }
        data = {"title": "Invalid File"}
        
        response = await authenticated_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
        )
        
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"].lower()
    
    async def test_get_document(
        self,
        authenticated_client: AsyncClient,
        db_session,
        test_tenant,
        test_user,
    ):
        """Test getting single document."""
        doc = await DocumentFactory.create(
            db_session,
            test_tenant,
            test_user,
            title="Specific Document",
        )
        
        response = await authenticated_client.get(
            f"/api/v1/documents/{doc.id}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == doc.id
        assert data["title"] == "Specific Document"
    
    async def test_get_document_wrong_tenant(
        self,
        authenticated_client: AsyncClient,
        db_session,
        test_user,
    ):
        """Test accessing document from another tenant (should fail)."""
        # Create another tenant and document
        from tests.factories import TenantFactory
        
        other_tenant = await TenantFactory.create(db_session)
        other_user = await UserFactory.create(db_session, other_tenant)
        other_doc = await DocumentFactory.create(
            db_session,
            other_tenant,
            other_user,
        )
        
        # Try to access with first tenant's credentials
        response = await authenticated_client.get(
            f"/api/v1/documents/{other_doc.id}"
        )
        
        assert response.status_code == 404  # Not found (tenant isolation)
    
    async def test_update_document(
        self,
        authenticated_client: AsyncClient,
        db_session,
        test_tenant,
        test_user,
    ):
        """Test updating document metadata."""
        doc = await DocumentFactory.create(
            db_session,
            test_tenant,
            test_user,
        )
        
        response = await authenticated_client.patch(
            f"/api/v1/documents/{doc.id}",
            json={"title": "Updated Title"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["title"] == "Updated Title"
    
    async def test_delete_document(
        self,
        authenticated_client: AsyncClient,
        db_session,
        test_tenant,
        test_user,
    ):
        """Test soft deleting document."""
        doc = await DocumentFactory.create(
            db_session,
            test_tenant,
            test_user,
        )
        
        response = await authenticated_client.delete(
            f"/api/v1/documents/{doc.id}"
        )
        
        assert response.status_code == 200
        assert "trash" in response.json()["message"].lower()
        
        # Document should still exist but marked deleted
        from sqlalchemy import select
        from app.models import Document
        
        result = await db_session.execute(
            select(Document).where(Document.id == doc.id)
        )
        deleted_doc = result.scalar_one()
        
        assert deleted_doc.is_deleted is True


@pytest.mark.api
class TestDocumentV2Endpoints:
    """Test V2 document endpoints (cursor pagination, bulk ops)."""
    
    async def test_cursor_pagination(
        self,
        authenticated_client: AsyncClient,
        db_session,
        test_tenant,
        test_user,
    ):
        """Test cursor-based pagination."""
        # Create documents
        await DocumentFactory.create_batch(
            db_session,
            test_tenant,
            test_user,
            count=20,
        )
        
        # First page
        response = await authenticated_client.get(
            "/api/v2/documents/?limit=10"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 10
        assert data["has_next"] is True
        assert data["next_cursor"] is not None
        
        # Next page
        next_cursor = data["next_cursor"]
        response = await authenticated_client.get(
            f"/api/v2/documents/?cursor={next_cursor}&limit=10"
        )
        
        assert response.status_code == 200
        next_data = response.json()
        
        assert len(next_data["items"]) >= 10
        
        # Items should be different
        first_ids = {item["id"] for item in data["items"]}
        second_ids = {item["id"] for item in next_data["items"]}
        assert first_ids.isdisjoint(second_ids)
    
    async def test_bulk_archive(
        self,
        authenticated_client: AsyncClient,
        db_session,
        test_tenant,
        test_user,
    ):
        """Test bulk archive operation."""
        # Create documents
        docs = await DocumentFactory.create_batch(
            db_session,
            test_tenant,
            test_user,
            count=5,
        )
        
        doc_ids = [doc.id for doc in docs]
        
        response = await authenticated_client.post(
            "/api/v2/documents/bulk",
            json={
                "document_ids": doc_ids,
                "action": "archive",
            },
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["succeeded"] == 5
        assert result["failed"] == 0
        assert result["total_requested"] == 5