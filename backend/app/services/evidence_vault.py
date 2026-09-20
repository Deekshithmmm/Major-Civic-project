"""
Module 4's evidence vault (spec 2.5). Separate from `services/storage.py` on purpose: that
module writes the general media bucket that public pages read from, and this one writes a bucket
nothing public ever reads.

The sealing hash is taken over the ORIGINAL bytes, before any processing. A hash computed after
the server re-encoded the file proves nothing about what the reporter actually submitted, which
is the whole point of a chain of custody.
"""

import hashlib

from app.config import get_settings
from app.services.storage import get_s3_client, presigned_url, put_object

settings = get_settings()


def seal(data: bytes) -> str:
    """SHA-256 of the original upload, computed before anything touches it."""
    return hashlib.sha256(data).hexdigest()


def store_evidence(data: bytes, content_type: str) -> str:
    """Write to the evidence vault bucket. Never the general media bucket."""
    return put_object(
        data,
        content_type,
        bucket=settings.s3_bucket_evidence_vault,
        key_prefix="module4/evidence",
    )


def evidence_url(key: str, expires_seconds: int = 120) -> str:
    """
    Short-lived link for an authorised investigating officer. Deliberately brief: a link that
    outlives the officer's session is a copy of the evidence that nobody is logging.
    """
    return presigned_url(key, bucket=settings.s3_bucket_evidence_vault, expires_seconds=expires_seconds)


def vault_object_exists(key: str) -> bool:
    client = get_s3_client()
    try:
        client.head_object(Bucket=settings.s3_bucket_evidence_vault, Key=key)
        return True
    except Exception:
        return False
