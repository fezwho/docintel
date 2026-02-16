"""
Document management endpoints.
"""

import logging
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.features.auth.dependencies import CurrentUser, require_permission
from app.features.documents.service import document_service
from app.features.documents.storage import get_storage
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.document import (
    DocumentFilter,
    DocumentRead,
    DocumentStats,
    DocumentUpdate,
    DocumentUploadResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(..., description="Document file to upload"),
    title: str = Form(..., description="Document title"),
    description: str | None = Form(None, description="Document description"),
    current_user: CurrentUser = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> DocumentUploadResponse:
    """
    Upload a new document.
    
    Accepts:
    - PDF (.pdf)
    - Word (.docx)
    - Text (.txt)
    - Markdown (.md)
    
    Maximum file size: 10MB
    """
    document = await document_service.create_document(
        db=db,
        file=file,
        title=title,
        description=description,
        current_user=current_user,
    )
    
    return DocumentUploadResponse(
        document=DocumentRead.model_validate(document),
        message=f"Document '{document.title}' uploaded successfully",
    )


@router.get("/", response_model=PaginatedResponse[DocumentRead])
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: str | None = Query(None, description="Filter by status"),
    document_type: str | None = Query(None, description="Filter by type"),
    search: str | None = Query(None, description="Search in title/description"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    current_user: CurrentUser = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> PaginatedResponse[DocumentRead]:
    """
    List documents with filtering, sorting, and pagination.
    
    Query parameters:
    - skip: Number of records to skip
    - limit: Maximum records to return (max 100)
    - status: Filter by status (pending, processing, completed, failed)
    - document_type: Filter by type (pdf, word, text, markdown)
    - search: Search term for title/description
    - sort_by: Field to sort by (created_at, title, file_size)
    - sort_order: Sort direction (asc, desc)
    """
    filters = DocumentFilter(
        status=status,
        document_type=document_type,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    
    documents, total = await document_service.list_documents(
        db=db,
        current_user=current_user,
        filters=filters,
        skip=skip,
        limit=limit,
    )
    
    return PaginatedResponse(
        items=[DocumentRead.model_validate(doc) for doc in documents],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/stats", response_model=DocumentStats)
async def get_document_stats(
    current_user: CurrentUser = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> DocumentStats:
    """
    Get document statistics for current tenant.
    
    Returns:
    - Total document count
    - Total storage used
    - Breakdown by status
    - Breakdown by type
    - Recent uploads (last 7 days)
    """
    return await document_service.get_document_stats(db, current_user)


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: str,
    current_user: CurrentUser = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> DocumentRead:
    """Get document by ID."""
    document = await document_service.get_document(db, document_id, current_user)
    return DocumentRead.model_validate(document)


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: CurrentUser = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """
    Download document file.
    
    Returns the actual file content with appropriate headers.
    """
    document = await document_service.get_document(db, document_id, current_user)
    
    # Get file from storage
    storage = get_storage()
    file_content = await storage.get(document.file_path)
    
    # Return as streaming response
    from io import BytesIO
    
    return StreamingResponse(
        BytesIO(file_content),
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document.filename}"',
            "Content-Length": str(document.file_size),
        }
    )


@router.patch("/{document_id}", response_model=DocumentRead)
async def update_document(
    document_id: str,
    update_data: DocumentUpdate,
    current_user: CurrentUser = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> DocumentRead:
    """
    Update document metadata.
    
    Can update:
    - title
    - description
    - status
    - is_public flag
    """
    document = await document_service.update_document(
        db=db,
        document_id=document_id,
        update_data=update_data.model_dump(exclude_unset=True),
        current_user=current_user,
    )
    
    return DocumentRead.model_validate(document)


@router.delete("/{document_id}", response_model=MessageResponse)
async def delete_document(
    document_id: str,
    hard_delete: bool = Query(False, description="Permanently delete (admin only)"),
    current_user: CurrentUser = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> MessageResponse:
    """
    Delete document.
    
    - Soft delete (default): Mark as deleted, keep file
    - Hard delete (hard_delete=true): Permanently delete file and record (requires documents:delete permission)
    """
    if hard_delete and not current_user.has_permission("documents:delete"):
        from app.core.exceptions import forbidden
        raise forbidden("Permission 'documents:delete' required for hard delete")
    
    await document_service.delete_document(
        db=db,
        document_id=document_id,
        current_user=current_user,
        hard_delete=hard_delete,
    )
    
    return MessageResponse(
        message="Document deleted permanently" if hard_delete else "Document moved to trash"
    )