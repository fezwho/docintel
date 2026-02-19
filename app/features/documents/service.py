import logging
from datetime import datetime, timedelta
from io import BytesIO
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

# Metrics and Monitoring
from app.core.metrics import documents_uploaded_total, documents_processed_total
from app.core.performance import PerformanceMonitor

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
    """Document management service with integrated monitoring."""
    
    @staticmethod
    async def create_document(
        db: AsyncSession,
        file: UploadFile,
        title: str,
        description: str | None,
        current_user: User,
    ) -> Document:
        """
        Upload and create a new document with metric tracking.
        """
        # 1. Validation
        if not validate_file_extension(file.filename):
            raise bad_request(f"File type not allowed. Allowed types: .pdf, .docx, .txt, .md")
        
        content = await file.read()
        file_size = len(content)
        
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            raise bad_request("File size exceeds 10MB limit")
        
        if file_size == 0:
            raise bad_request("File is empty")
        
        # 2. Hash & Duplicate Check
        file_obj = BytesIO(content)
        file_hash = compute_file_hash(file_obj)
        
        result = await db.execute(
            select(Document).where(
                and_(
                    Document.tenant_id == current_user.tenant_id,
                    Document.file_hash == file_hash,
                    Document.is_deleted == False
                )
            )
        )
        if result.scalar_one_or_none():
            logger.info(f"Duplicate file detected: {file_hash} for tenant {current_user.tenant_id}")
        
        # 3. Storage & Classification
        file_path = generate_file_path(current_user.tenant_id, file.filename)
        storage = get_storage()
        file_obj.seek(0)
        await storage.save(file_obj, file_path)
        
        mime_type = get_mime_type(file.filename)
        document_type = DocumentService._classify_document_type(mime_type, file.filename)
        
        # 4. Database Record
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
        
        # 5. Metrics Increment
        documents_uploaded_total.labels(
            tenant_id=current_user.tenant_id,
            document_type=document_type.value,
        ).inc()
        
        logger.info(f"Document created: {document.id}. Queueing background task.")
        
        # 6. Background Task
        process_document.delay(
            document_id=document.id,
            tenant_id=current_user.tenant_id
        )
                
        return document

    @staticmethod
    async def list_documents(
        db: AsyncSession,
        current_user: User,
        filters: DocumentFilter,
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[Document], int]:
        """List documents with performance monitoring for complex filtering."""
        async with PerformanceMonitor("list_documents", tenant_id=current_user.tenant_id):
            query = select(Document).where(
                and_(
                    Document.tenant_id == current_user.tenant_id,
                    Document.is_deleted == filters.is_deleted
                )
            )
            
            # Apply dynamic filters
            if filters.status:
                query = query.where(Document.status == filters.status)
            if filters.document_type:
                query = query.where(Document.document_type == filters.document_type)
            if filters.search:
                search_term = f"%{filters.search}%"
                query = query.where(
                    or_(
                        Document.title.ilike(search_term),
                        Document.filename.ilike(search_term)
                    )
                )
            
            # Pagination & Execution
            total_result = await db.execute(select(func.count()).select_from(query.subquery()))
            total = total_result.scalar()
            
            sort_column = getattr(Document, filters.sort_by)
            query = query.order_by(sort_column.desc() if filters.sort_order == "desc" else sort_column.asc())
            query = query.offset(skip).limit(limit)
            
            result = await db.execute(query)
            return list(result.scalars().all()), total

    @staticmethod
    def _classify_document_type(mime_type: str, filename: str) -> DocumentType:
        ext = filename.lower().split(".")[-1]
        if "pdf" in mime_type or ext == "pdf":
            return DocumentType.PDF
        if "word" in mime_type or ext in ["doc", "docx"]:
            return DocumentType.WORD
        if "text" in mime_type or ext == "txt":
            return DocumentType.TEXT
        if ext in ["md", "markdown"]:
            return DocumentType.MARKDOWN
        return DocumentType.OTHER

    @staticmethod
    async def get_document(db: AsyncSession, document_id: str, current_user: User) -> Document:
        result = await db.execute(
            select(Document).where(
                and_(
                    Document.id == document_id,
                    Document.tenant_id == current_user.tenant_id,
                    Document.is_deleted == False
                )
            )
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise not_found("Document not found")
        return doc

    @staticmethod
    async def get_document_stats(db: AsyncSession, current_user: User) -> DocumentStats:
        """Fetch high-level aggregate stats for the tenant dashboard."""
        async with PerformanceMonitor("get_document_stats", tenant_id=current_user.tenant_id):
            # Aggregate queries...
            total_result = await db.execute(
                select(func.count(Document.id), func.sum(Document.file_size))
                .where(and_(Document.tenant_id == current_user.tenant_id, Document.is_deleted == False))
            )
            total_count, total_size = total_result.one()
            
            # simplified for brevity
            return DocumentStats(
                total_documents=total_count or 0,
                total_size_bytes=total_size or 0,
                total_size_mb=round((total_size or 0) / (1024 * 1024), 2)
            )

# Singleton instance
document_service = DocumentService()