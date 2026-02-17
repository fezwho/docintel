"""
Document business logic.
"""

import logging
from datetime import datetime, timedelta
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.documents.tasks import process_document
from app.core.exceptions import bad_request, not_found
from app.models.document import Document, DocumentStatus, DocumentType
from app.models.user import User
from app.schemas.document import DocumentCreate, DocumentFilter, DocumentStats
from app.features.documents.storage import (
    compute_file_hash,
    generate_file_path,
    get_mime_type,
    get_storage,
    validate_file_extension,
)

logger = logging.getLogger(__name__)


class DocumentService:
    """Document management service."""
    
    @staticmethod
    async def create_document(
        db: AsyncSession,
        file: UploadFile,
        title: str,
        description: str | None,
        current_user: User,
    ) -> Document:
        """
        Upload and create a new document.
        
        Args:
            db: Database session
            file: Uploaded file
            title: Document title
            description: Document description
            current_user: User uploading the document
            
        Returns:
            Created document object
            
        Raises:
            HTTPException: If validation fails
        """
        # Validate file extension
        if not validate_file_extension(file.filename):
            raise bad_request(f"File type not allowed. Allowed types: {', '.join(['.pdf', '.docx', '.txt', '.md'])}")
        
        # Validate file size
        content = await file.read()
        file_size = len(content)
        
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            raise bad_request("File size exceeds 10MB limit")
        
        if file_size == 0:
            raise bad_request("File is empty")
        
        # Compute file hash
        from io import BytesIO
        file_obj = BytesIO(content)
        file_hash = compute_file_hash(file_obj)
        
        # Check for duplicate (same hash in same tenant)
        result = await db.execute(
            select(Document).where(
                and_(
                    Document.tenant_id == current_user.tenant_id,
                    Document.file_hash == file_hash,
                    Document.is_deleted == False
                )
            )
        )
        existing_doc = result.scalar_one_or_none()
        
        if existing_doc:
            logger.info(f"Duplicate file detected: {file_hash}")
            # You could return the existing document or raise an error
            # For now, we'll allow duplicates but log them
        
        # Generate storage path
        file_path = generate_file_path(current_user.tenant_id, file.filename)
        
        # Save file to storage
        storage = get_storage()
        file_obj.seek(0)  # Reset pointer
        await storage.save(file_obj, file_path)
        
        # Determine document type
        mime_type = get_mime_type(file.filename)
        document_type = DocumentService._classify_document_type(mime_type, file.filename)
        
        # Create document record
        document = Document(
            title=title,
            description=description,
            filename=file.filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            document_type=document_type,
            status=DocumentStatus.PENDING,
            tenant_id=current_user.tenant_id,
            uploaded_by_user_id=current_user.id,
        )
        
        db.add(document)
        await db.commit()
        await db.refresh(document)
        
        logger.info(f"Document created: {document.id} ({file.filename})")
        
        logger.info(f"Document created: {document.id} ({file.filename})")
        
        # Queue background processing task
        task = process_document.delay(
            document_id=document.id,
            tenant_id=current_user.tenant_id
        )
        logger.info(f"Processing task queued: {task.id} for document {document.id}")
                
        return document
    
    @staticmethod
    def _classify_document_type(mime_type: str, filename: str) -> DocumentType:
        """Classify document type from MIME type and filename."""
        ext = filename.lower().split(".")[-1]
        
        if "pdf" in mime_type or ext == "pdf":
            return DocumentType.PDF
        elif "word" in mime_type or ext in ["doc", "docx"]:
            return DocumentType.WORD
        elif "text" in mime_type or ext == "txt":
            return DocumentType.TEXT
        elif ext in ["md", "markdown"]:
            return DocumentType.MARKDOWN
        else:
            return DocumentType.OTHER
    
    @staticmethod
    async def get_document(
        db: AsyncSession,
        document_id: str,
        current_user: User,
    ) -> Document:
        """Get document by ID with tenant check."""
        result = await db.execute(
            select(Document).where(
                and_(
                    Document.id == document_id,
                    Document.tenant_id == current_user.tenant_id,
                    Document.is_deleted == False
                )
            )
        )
        
        document = result.scalar_one_or_none()
        
        if not document:
            raise not_found("Document not found")
        
        return document
    
    @staticmethod
    async def list_documents(
        db: AsyncSession,
        current_user: User,
        filters: DocumentFilter,
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[Document], int]:
        """
        List documents with filtering and pagination.
        
        Returns:
            Tuple of (documents, total_count)
        """
        # Build query
        query = select(Document).where(
            Document.tenant_id == current_user.tenant_id
        )
        
        # Apply filters
        if filters.status:
            query = query.where(Document.status == filters.status)
        
        if filters.document_type:
            query = query.where(Document.document_type == filters.document_type)
        
        if filters.uploaded_by_user_id:
            query = query.where(Document.uploaded_by_user_id == filters.uploaded_by_user_id)
        
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.where(
                or_(
                    Document.title.ilike(search_term),
                    Document.description.ilike(search_term),
                    Document.filename.ilike(search_term)
                )
            )
        
        if filters.created_after:
            query = query.where(Document.created_at >= filters.created_after)
        
        if filters.created_before:
            query = query.where(Document.created_at <= filters.created_before)
        
        query = query.where(Document.is_deleted == filters.is_deleted)
        
        # Get total count (before pagination)
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply sorting
        sort_column = getattr(Document, filters.sort_by)
        if filters.sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        # Execute query
        result = await db.execute(query)
        documents = result.scalars().all()
        
        return list(documents), total
    
    @staticmethod
    async def update_document(
        db: AsyncSession,
        document_id: str,
        update_data: dict,
        current_user: User,
    ) -> Document:
        """Update document metadata."""
        document = await DocumentService.get_document(db, document_id, current_user)
        
        # Update fields
        for field, value in update_data.items():
            if value is not None:
                setattr(document, field, value)
        
        await db.commit()
        await db.refresh(document)
        
        logger.info(f"Document updated: {document_id}")
        
        return document
    
    @staticmethod
    async def delete_document(
        db: AsyncSession,
        document_id: str,
        current_user: User,
        hard_delete: bool = False,
    ) -> bool:
        """
        Delete document (soft or hard).
        
        Args:
            db: Database session
            document_id: Document ID
            current_user: Current user
            hard_delete: If True, permanently delete file and record
            
        Returns:
            True if deleted
        """
        document = await DocumentService.get_document(db, document_id, current_user)
        
        if hard_delete:
            # Delete file from storage
            storage = get_storage()
            await storage.delete(document.file_path)
            
            # Delete database record
            await db.delete(document)
            logger.info(f"Document hard deleted: {document_id}")
        else:
            # Soft delete
            document.is_deleted = True
            logger.info(f"Document soft deleted: {document_id}")
        
        await db.commit()
        return True
    
    @staticmethod
    async def get_document_stats(
        db: AsyncSession,
        current_user: User,
    ) -> DocumentStats:
        """Get document statistics for tenant."""
        # Total documents
        total_result = await db.execute(
            select(func.count(Document.id)).where(
                and_(
                    Document.tenant_id == current_user.tenant_id,
                    Document.is_deleted == False
                )
            )
        )
        total_documents = total_result.scalar()
        
        # Total size
        size_result = await db.execute(
            select(func.sum(Document.file_size)).where(
                and_(
                    Document.tenant_id == current_user.tenant_id,
                    Document.is_deleted == False
                )
            )
        )
        total_size_bytes = size_result.scalar() or 0
        
        # By status
        status_result = await db.execute(
            select(
                Document.status,
                func.count(Document.id)
            ).where(
                and_(
                    Document.tenant_id == current_user.tenant_id,
                    Document.is_deleted == False
                )
            ).group_by(Document.status)
        )
        by_status = {row[0]: row[1] for row in status_result}
        
        # By type
        type_result = await db.execute(
            select(
                Document.document_type,
                func.count(Document.id)
            ).where(
                and_(
                    Document.tenant_id == current_user.tenant_id,
                    Document.is_deleted == False
                )
            ).group_by(Document.document_type)
        )
        by_type = {row[0]: row[1] for row in type_result}
        
        # Recent uploads (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_result = await db.execute(
            select(func.count(Document.id)).where(
                and_(
                    Document.tenant_id == current_user.tenant_id,
                    Document.is_deleted == False,
                    Document.created_at >= week_ago
                )
            )
        )
        recent_uploads = recent_result.scalar()
        
        return DocumentStats(
            total_documents=total_documents,
            total_size_bytes=total_size_bytes,
            total_size_mb=round(total_size_bytes / (1024 * 1024), 2),
            by_status=by_status,
            by_type=by_type,
            recent_uploads=recent_uploads,
        )


# Singleton instance
document_service = DocumentService()