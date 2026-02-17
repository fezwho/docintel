"""
Document router v2 with:
- Cursor-based pagination
- Cached responses
- Bulk operations
- Rate limiting
- Optimized queries
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_manager
from app.core.database import get_db
from app.core.query_helpers import QueryBuilder
from app.core.rate_limit import rate_limit
from app.features.auth.dependencies import CurrentUser
from app.features.documents.bulk_schemas import (
    BulkDocumentAction,
    BulkOperationResult,
    BulkUpdateSchema,
)
from app.models.document import Document, DocumentStatus
from app.schemas.document import DocumentRead
from app.schemas.pagination import CursorPage, CursorParams

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents V2"])


@router.get(
    "/",
    response_model=CursorPage[DocumentRead],
    summary="List documents with cursor pagination",
)
async def list_documents_v2(
    cursor: str | None = Query(None, description="Pagination cursor"),
    limit: int = Query(10, ge=1, le=100),
    search: str | None = Query(None, description="Search term"),
    status: str | None = Query(None, description="Filter by status"),
    current_user: CurrentUser = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _rate_limit: dict = Depends(rate_limit("search")),
) -> CursorPage[DocumentRead]:
    """
    List documents with cursor-based pagination.
    
    V2 uses cursor pagination for:
    - Consistent results (no skipped items on new inserts)
    - Efficient deep pagination
    - Better performance on large datasets
    """
    # Build cache key
    cache_key = f"{current_user.tenant_id}:cursor:{cursor}:{limit}:{search}:{status}"
    
    # Try cache first
    cached = await cache_manager.get("documents_v2", cache_key)
    if cached:
        logger.debug(f"Cache hit for document list: {current_user.tenant_id}")
        return CursorPage[DocumentRead](**cached)
    
    # Build query with optimizations
    builder = QueryBuilder(db, Document)
    builder.filter(
        Document.tenant_id == current_user.tenant_id,
        Document.is_deleted == False,
    )
    
    if status:
        builder.filter(Document.status == status)
    
    if search:
        from sqlalchemy import or_
        builder.filter(
            or_(
                Document.title.ilike(f"%{search}%"),
                Document.filename.ilike(f"%{search}%"),
            )
        )
    
    # Execute with cursor pagination
    items, next_cursor, prev_cursor = await builder.execute_cursor(
        cursor_field=Document.created_at,
        cursor=cursor,
        limit=limit,
    )
    
    response = CursorPage(
        items=[DocumentRead.model_validate(doc) for doc in items],
        next_cursor=next_cursor,
        prev_cursor=prev_cursor,
        has_next=next_cursor is not None,
        has_prev=prev_cursor is not None,
    )
    
    # Cache the response
    await cache_manager.set(
        "documents_v2",
        cache_key,
        response.model_dump(),
        ttl=60,  # Cache for 60 seconds
    )
    
    return response


@router.post(
    "/bulk",
    response_model=BulkOperationResult,
    summary="Bulk document operations",
)
async def bulk_document_action(
    bulk_action: BulkDocumentAction,
    current_user: CurrentUser = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _rate_limit: dict = Depends(rate_limit("bulk")),
) -> BulkOperationResult:
    """
    Perform bulk operations on multiple documents.
    
    Supported actions:
    - **delete**: Soft delete documents
    - **archive**: Set status to archived
    - **restore**: Restore soft-deleted documents
    - **reprocess**: Re-queue failed documents for processing
    
    Max 100 documents per request.
    Rate limited: 5 requests/minute.
    """
    from sqlalchemy import select
    
    succeeded = 0
    failed = 0
    skipped = 0
    errors = []
    
    # Fetch all documents in one query (N+1 prevention)
    result = await db.execute(
        select(Document).where(
            and_(
                Document.id.in_(bulk_action.document_ids),
                Document.tenant_id == current_user.tenant_id,
            )
        )
    )
    documents = {doc.id: doc for doc in result.scalars().all()}
    
    # Process each document
    for doc_id in bulk_action.document_ids:
        doc = documents.get(doc_id)
        
        if not doc:
            skipped += 1
            errors.append({
                "id": doc_id,
                "error": "Document not found or access denied"
            })
            continue
        
        try:
            if bulk_action.action == "delete":
                doc.is_deleted = True
                succeeded += 1
            
            elif bulk_action.action == "archive":
                doc.status = DocumentStatus.ARCHIVED
                succeeded += 1
            
            elif bulk_action.action == "restore":
                if not doc.is_deleted:
                    skipped += 1
                    continue
                doc.is_deleted = False
                succeeded += 1
            
            elif bulk_action.action == "reprocess":
                if doc.status not in [DocumentStatus.FAILED, DocumentStatus.COMPLETED]:
                    skipped += 1
                    continue
                doc.status = DocumentStatus.PENDING
                doc.error_message = None
                
                # Queue reprocessing
                from app.features.documents.tasks import process_document
                process_document.delay(doc.id, current_user.tenant_id)
                
                succeeded += 1
        
        except Exception as e:
            failed += 1
            errors.append({"id": doc_id, "error": str(e)})
    
    # Commit all changes in one transaction
    await db.commit()
    
    # Invalidate cache
    await cache_manager.invalidate_namespace("documents_v2")
    
    logger.info(
        f"Bulk action '{bulk_action.action}': "
        f"{succeeded} succeeded, {failed} failed, {skipped} skipped"
    )
    
    return BulkOperationResult(
        total_requested=len(bulk_action.document_ids),
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        errors=errors,
    )


@router.patch(
    "/bulk-update",
    response_model=BulkOperationResult,
    summary="Bulk update document metadata",
)
async def bulk_update_documents(
    bulk_update: BulkUpdateSchema,
    current_user: CurrentUser = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _rate_limit: dict = Depends(rate_limit("bulk")),
) -> BulkOperationResult:
    """
    Update metadata for multiple documents.
    
    Allowed update fields:
    - is_public: bool
    - title: str
    - description: str
    
    Max 100 documents per request.
    """
    from sqlalchemy import select
    
    # Whitelist of updatable fields
    allowed_fields = {"is_public", "title", "description"}
    invalid_fields = set(bulk_update.updates.keys()) - allowed_fields
    
    if invalid_fields:
        from app.core.exceptions import bad_request
        raise bad_request(f"Cannot bulk update fields: {invalid_fields}")
    
    # Fetch documents in single query
    result = await db.execute(
        select(Document).where(
            and_(
                Document.id.in_(bulk_update.document_ids),
                Document.tenant_id == current_user.tenant_id,
                Document.is_deleted == False,
            )
        )
    )
    documents = result.scalars().all()
    found_ids = {doc.id for doc in documents}
    
    succeeded = 0
    skipped = len(bulk_update.document_ids) - len(found_ids)
    errors = []
    
    # Apply updates
    for doc in documents:
        try:
            for field, value in bulk_update.updates.items():
                setattr(doc, field, value)
            succeeded += 1
        except Exception as e:
            errors.append({"id": doc.id, "error": str(e)})
    
    await db.commit()
    
    # Invalidate cache
    await cache_manager.invalidate_namespace("documents_v2")
    
    return BulkOperationResult(
        total_requested=len(bulk_update.document_ids),
        succeeded=succeeded,
        failed=len(errors),
        skipped=skipped,
        errors=errors,
    )