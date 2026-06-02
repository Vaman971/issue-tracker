"""File storage service.

Supports two backends controlled by settings.STORAGE_BACKEND:
  - "local"  — stores files under settings.LOCAL_UPLOAD_DIR (great for dev)
  - "s3"     — stores files in an AWS S3 bucket

Public API:
    upload_file(data, filename, mime_type) -> str  (storage key)
    delete_file(key) -> None
    get_download_url(key) -> str
"""

import logging
import mimetypes
import os
import uuid
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# Allowed MIME types for uploads
ALLOWED_MIME_TYPES: set[str] = {
    # images
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    # documents
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/csv",
    # archives
    "application/zip",
    "application/x-tar",
    "application/gzip",
}

MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def _safe_filename(original: str) -> str:
    """Return a UUID-based filename preserving the original extension."""
    ext = Path(original).suffix.lower()
    return f"{uuid.uuid4().hex}{ext}"


# ---------------------------------------------------------------------------
# Local backend
# ---------------------------------------------------------------------------

def _local_upload_dir() -> Path:
    d = Path(settings.LOCAL_UPLOAD_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _local_save(data: bytes, filename: str) -> str:
    import aiofiles

    key = _safe_filename(filename)
    dest = _local_upload_dir() / key
    async with aiofiles.open(dest, "wb") as f:
        await f.write(data)
    return key


async def _local_delete(key: str) -> None:
    path = _local_upload_dir() / key
    try:
        path.unlink(missing_ok=True)
    except Exception:
        logger.exception("Failed to delete local file: %s", key)


def _local_url(key: str) -> str:
    return f"/files/{key}"


# ---------------------------------------------------------------------------
# S3 backend
# ---------------------------------------------------------------------------

def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    )


async def _s3_upload(data: bytes, original_filename: str, mime_type: str) -> str:
    import asyncio

    key = f"uploads/{_safe_filename(original_filename)}"

    def _do_upload():
        client = _s3_client()
        client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=mime_type,
        )

    await asyncio.get_event_loop().run_in_executor(None, _do_upload)
    return key


async def _s3_delete(key: str) -> None:
    import asyncio

    def _do_delete():
        client = _s3_client()
        client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)

    try:
        await asyncio.get_event_loop().run_in_executor(None, _do_delete)
    except Exception:
        logger.exception("Failed to delete S3 object: %s", key)


def _s3_presigned_url(key: str) -> str:
    client = _s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": key},
        ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRES_SECONDS,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_upload(data: bytes, mime_type: str) -> None:
    """Raise ValueError if the upload is invalid."""
    if len(data) > MAX_BYTES:
        raise ValueError(f"File size exceeds maximum of {settings.MAX_UPLOAD_SIZE_MB} MB")
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"File type '{mime_type}' is not allowed")


async def upload_file(data: bytes, original_filename: str, mime_type: str) -> str:
    """Save the file and return its storage key."""
    validate_upload(data, mime_type)
    if settings.STORAGE_BACKEND == "s3":
        return await _s3_upload(data, original_filename, mime_type)
    return await _local_save(data, original_filename)


async def delete_file(key: str) -> None:
    if settings.STORAGE_BACKEND == "s3":
        await _s3_delete(key)
    else:
        await _local_delete(key)


def get_download_url(key: str) -> str:
    if settings.STORAGE_BACKEND == "s3":
        return _s3_presigned_url(key)
    return _local_url(key)
