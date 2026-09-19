"""
S3-compatible object storage client (MinIO for local dev). Video and image evidence is never
stored in the database (spec 2.1) - only an opaque media ID (the object key) is persisted in
SQL rows, and this module is the only place that touches the storage backend directly.
"""

import uuid
from functools import lru_cache
from io import BytesIO

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import get_settings

settings = get_settings()


@lru_cache
def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=BotoConfig(signature_version="s3v4"),
        region_name=settings.s3_region,
    )


def ensure_buckets() -> None:
    """Create the general media bucket and the segregated evidence vault bucket if absent."""
    client = get_s3_client()
    for bucket in (settings.s3_bucket_media, settings.s3_bucket_evidence_vault):
        try:
            client.head_bucket(Bucket=bucket)
        except ClientError:
            client.create_bucket(Bucket=bucket)


def put_object(data: bytes, content_type: str, bucket: str | None = None, key_prefix: str = "media") -> str:
    """Write bytes to object storage, return an opaque media ID (the object key)."""
    client = get_s3_client()
    bucket = bucket or settings.s3_bucket_media
    key = f"{key_prefix}/{uuid.uuid4().hex}"
    client.put_object(Bucket=bucket, Key=key, Body=BytesIO(data), ContentType=content_type)
    return key


def get_object(key: str, bucket: str | None = None) -> bytes:
    client = get_s3_client()
    bucket = bucket or settings.s3_bucket_media
    response = client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def presigned_url(key: str, bucket: str | None = None, expires_seconds: int = 300) -> str:
    client = get_s3_client()
    bucket = bucket or settings.s3_bucket_media
    return client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires_seconds
    )
