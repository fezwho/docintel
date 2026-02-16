"""
File storage abstraction layer.

Provides unified interface for local filesystem and S3-compatible storage.
Switch between storage backends via configuration.
"""

import hashlib
import logging
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

from app.config import settings

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract storage backend interface."""
    
    @abstractmethod
    async def save(self, file: BinaryIO, path: str) -> str:
        """
        Save file to storage.
        
        Args:
            file: File-like object to save
            path: Storage path/key
            
        Returns:
            Full storage path/URL
        """
        pass
    
    @abstractmethod
    async def delete(self, path: str) -> bool:
        """
        Delete file from storage.
        
        Args:
            path: Storage path/key
            
        Returns:
            True if deleted, False if not found
        """
        pass
    
    @abstractmethod
    async def get(self, path: str) -> bytes:
        """
        Retrieve file from storage.
        
        Args:
            path: Storage path/key
            
        Returns:
            File contents as bytes
        """
        pass
    
    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if file exists."""
        pass
    
    @abstractmethod
    def get_url(self, path: str) -> str:
        """Get access URL for file."""
        pass


class LocalFileStorage(StorageBackend):
    """
    Local filesystem storage.
    
    Stores files in a directory structure:
    uploads/
      ├── tenants/
      │   └── {tenant_id}/
      │       └── {year}/
      │           └── {month}/
      │               └── {filename}
    """
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path or settings.upload_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized local storage: {self.base_path}")
    
    def _get_full_path(self, path: str) -> Path:
        """Get full filesystem path."""
        return self.base_path / path
    
    async def save(self, file: BinaryIO, path: str) -> str:
        """Save file to local filesystem."""
        full_path = self._get_full_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        with open(full_path, "wb") as f:
            shutil.copyfileobj(file, f)
        
        logger.info(f"File saved: {path}")
        return path
    
    async def delete(self, path: str) -> bool:
        """Delete file from filesystem."""
        full_path = self._get_full_path(path)
        
        if full_path.exists():
            full_path.unlink()
            logger.info(f"File deleted: {path}")
            return True
        
        logger.warning(f"File not found for deletion: {path}")
        return False
    
    async def get(self, path: str) -> bytes:
        """Read file from filesystem."""
        full_path = self._get_full_path(path)
        
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        with open(full_path, "rb") as f:
            return f.read()
    
    async def exists(self, path: str) -> bool:
        """Check if file exists."""
        return self._get_full_path(path).exists()
    
    def get_url(self, path: str) -> str:
        """
        Get file URL.
        
        For local storage, this would be a route like /files/{path}
        In production with S3, this would be a signed URL.
        """
        return f"/api/v1/documents/files/{path}"


class S3Storage(StorageBackend):
    """
    S3-compatible storage (AWS S3, MinIO, etc.).
    
    NOTE: Not implemented in this milestone (free local setup).
    This is the interface for future S3 integration.
    """
    
    def __init__(self, bucket: str, endpoint: str = None):
        self.bucket = bucket
        self.endpoint = endpoint
        logger.warning("S3Storage not implemented - using LocalFileStorage")
    
    async def save(self, file: BinaryIO, path: str) -> str:
        raise NotImplementedError("S3 storage not implemented")
    
    async def delete(self, path: str) -> bool:
        raise NotImplementedError("S3 storage not implemented")
    
    async def get(self, path: str) -> bytes:
        raise NotImplementedError("S3 storage not implemented")
    
    async def exists(self, path: str) -> bool:
        raise NotImplementedError("S3 storage not implemented")
    
    def get_url(self, path: str) -> str:
        raise NotImplementedError("S3 storage not implemented")


# Storage factory
def get_storage() -> StorageBackend:
    """
    Get storage backend based on configuration.
    
    Returns:
        Configured storage backend instance
    """
    # For now, always use local storage
    # In production, check settings.storage_backend and return appropriate class
    return LocalFileStorage()


# Utility functions
def compute_file_hash(file: BinaryIO) -> str:
    """
    Compute SHA256 hash of file.
    
    Useful for:
    - Deduplication (don't store same file twice)
    - Integrity verification
    - Change detection
    """
    sha256 = hashlib.sha256()
    
    # Reset file pointer
    file.seek(0)
    
    # Read in chunks for memory efficiency
    for chunk in iter(lambda: file.read(8192), b""):
        sha256.update(chunk)
    
    # Reset file pointer again
    file.seek(0)
    
    return sha256.hexdigest()


def generate_file_path(tenant_id: str, filename: str) -> str:
    """
    Generate organized file path.
    
    Format: tenants/{tenant_id}/{year}/{month}/{uuid}_{filename}
    
    Args:
        tenant_id: Tenant ID
        filename: Original filename
        
    Returns:
        Relative storage path
    """
    import uuid
    from datetime import datetime
    
    now = datetime.utcnow()
    year = now.strftime("%Y")
    month = now.strftime("%m")
    
    # Add UUID to prevent filename conflicts
    unique_filename = f"{uuid.uuid4()}_{filename}"
    
    return f"tenants/{tenant_id}/{year}/{month}/{unique_filename}"


def get_mime_type(filename: str) -> str:
    """
    Determine MIME type from filename extension.
    
    Args:
        filename: Filename with extension
        
    Returns:
        MIME type string
    """
    import mimetypes
    
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def validate_file_extension(filename: str) -> bool:
    """
    Validate file extension against allowed list.
    
    Args:
        filename: Filename to validate
        
    Returns:
        True if extension is allowed
    """
    ext = Path(filename).suffix.lower()
    return ext in settings.allowed_extensions