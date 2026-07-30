"""Document storage - Cloudflare R2 via the S3-compatible API.

R2 buckets aren't region-pinned in the AWS sense, so boto3 is configured
with region_name="auto" per Cloudflare's own integration docs.
"""

from __future__ import annotations

import re
import uuid
from uuid import UUID

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import settings

_UNSAFE_HEADER_CHARS = re.compile(r'[\r\n"]')


class ObjectStorageError(Exception):
    """Raised when R2 is not configured, or a storage operation fails."""


class ObjectNotFoundError(ObjectStorageError):
    """Raised when a storage key no longer resolves to a real object in R2 -
    e.g. it was deleted directly in the R2 dashboard, outside the app,
    leaving the database's reference to it orphaned."""


def _client():
    if not (settings.r2_endpoint_url and settings.r2_access_key_id and settings.r2_secret_access_key):
        raise ObjectStorageError("Document storage is not configured")
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=BotoConfig(signature_version="s3v4"),
        region_name="auto",
    )


def upload(business_id: UUID, entity_type: str, entity_id: UUID, filename: str, content: bytes, content_type: str) -> str:
    """Upload a file, scoped under the tenant/entity in the object key. Returns the storage key."""
    storage_key = f"{business_id}/{entity_type}/{entity_id}/{uuid.uuid4()}-{filename}"
    try:
        _client().put_object(
            Bucket=settings.r2_bucket_name,
            Key=storage_key,
            Body=content,
            ContentType=content_type or "application/octet-stream",
        )
    except Exception as e:
        raise ObjectStorageError(f"Upload failed: {e}") from e
    return storage_key


def upload_at_key(key: str, content: bytes, content_type: str) -> None:
    """Upload content at an exact, caller-chosen key, overwriting whatever was
    there before - unlike upload(), which always mints a fresh uuid4() key.

    Used for the document editor's autosave draft buffer: the key is
    deterministic (derived from the document id alone), so repeated autosave
    calls overwrite the same object in place instead of accumulating
    orphaned ones.
    """
    try:
        _client().put_object(
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=content,
            ContentType=content_type or "application/octet-stream",
        )
    except Exception as e:
        raise ObjectStorageError(f"Upload failed: {e}") from e


def get(storage_key: str) -> bytes:
    """Fetch an object's raw content directly (not a presigned URL) - used
    server-side, e.g. reading back a draft buffer to fold into a real
    version, or the source file when duplicating a document."""
    try:
        return _client().get_object(Bucket=settings.r2_bucket_name, Key=storage_key)["Body"].read()
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
            raise ObjectNotFoundError(f"Object not found: {storage_key}") from e
        raise ObjectStorageError(f"Download failed: {e}") from e
    except Exception as e:
        raise ObjectStorageError(f"Download failed: {e}") from e


def presigned_download_url(storage_key: str, filename: str, expires_in: int = 300) -> str:
    """A short-lived, signed URL for downloading a private object directly from R2.

    Confirms the object actually exists first - generate_presigned_url() is a
    local signing operation with no network round-trip, so on its own it
    would happily mint a working-looking URL for a key that was deleted out
    from under the app (e.g. by hand, in the R2 dashboard), leaving callers
    to send the user to a raw, unstyled R2 XML error page.
    """
    client = _client()
    try:
        client.head_object(Bucket=settings.r2_bucket_name, Key=storage_key)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
            raise ObjectNotFoundError(f"Object not found: {storage_key}") from e
        raise ObjectStorageError(f"Failed to verify file exists: {e}") from e

    safe_filename = _UNSAFE_HEADER_CHARS.sub("", filename)
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.r2_bucket_name,
                "Key": storage_key,
                "ResponseContentDisposition": f'attachment; filename="{safe_filename}"',
            },
            ExpiresIn=expires_in,
        )
    except Exception as e:
        raise ObjectStorageError(f"Failed to generate download URL: {e}") from e


def delete(storage_key: str) -> None:
    try:
        _client().delete_object(Bucket=settings.r2_bucket_name, Key=storage_key)
    except Exception as e:
        raise ObjectStorageError(f"Delete failed: {e}") from e
