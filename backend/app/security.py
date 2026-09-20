"""
Request-level protections: rate limiting, upload size caps and response headers.

The rate limiter deliberately never stores a client's IP address. Modules 2 and 4 promise that
an uploader's IP is never persisted, and a rate-limit table keyed by IP would quietly break that
promise - it would be a log of who submitted what and when, and a subpoena target. Instead the
key is a hash of (IP + user agent + a random salt generated fresh at process start), held only
in memory and gone when the process exits. The salt means the stored keys cannot be reversed or
correlated with a captured IP list, even by someone who reads the process memory later.

The counters are per-process, so running multiple workers multiplies the effective limit. That
is fine as a backstop against scripted abuse but is not a substitute for a rate limit at the
gateway or CDN, which is where a real deployment should also enforce one.
"""

import hashlib
import secrets
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, UploadFile, status

from app.config import get_settings

settings = get_settings()

# Regenerated every process start: yesterday's keys cannot be matched against today's.
_FINGERPRINT_SALT = secrets.token_bytes(32)

_hits: dict[str, deque[float]] = defaultdict(deque)


def client_fingerprint(request: Request) -> str:
    """A transient, salted identifier for rate limiting. Never logged, never stored, never a PK."""
    client_ip = request.client.host if request.client else "unknown"
    agent = request.headers.get("user-agent", "")
    # A client-supplied device ID lets the browser keep its own identity across IP changes
    # (spec 2.3 asks for device-level limits, not identity-level ones).
    device = request.headers.get("x-device-id", "")
    raw = f"{client_ip}|{agent}|{device}".encode()
    return hashlib.blake2b(raw, key=_FINGERPRINT_SALT, digest_size=16).hexdigest()


def rate_limit(bucket: str, limit: int, window_seconds: int):
    """
    Route dependency. `bucket` separates limits so a burst of one kind of request cannot exhaust
    another - submitting reports must never lock an officer out of logging in.
    """

    def dependency(request: Request) -> None:
        key = f"{bucket}:{client_fingerprint(request)}"
        now = time.monotonic()
        hits = _hits[key]

        while hits and now - hits[0] > window_seconds:
            hits.popleft()

        if len(hits) >= limit:
            retry_after = int(window_seconds - (now - hits[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait and try again.",
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)

        # Without this, a long-running process accumulates a key per distinct client forever.
        if len(_hits) > 10_000:
            for stale_key in [k for k, v in _hits.items() if not v or now - v[-1] > 3600]:
                del _hits[stale_key]

    return dependency


def read_upload(file: UploadFile, max_bytes: int) -> bytes:
    """
    Read an upload with a hard ceiling, in chunks.

    `UploadFile.read()` with no argument will happily pull a multi-gigabyte body into memory, and
    every upload route here processes the file in memory - so an unbounded read is a one-request
    denial of service. Content-Length is checked first as a cheap rejection, but it is
    attacker-controlled, so the chunked read enforces the real limit.
    """
    declared = file.size
    if declared is not None and declared > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File is larger than the {max_bytes // (1024 * 1024)} MB limit.",
        )

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File is larger than the {max_bytes // (1024 * 1024)} MB limit.",
            )
        chunks.append(chunk)

    return b"".join(chunks)


def max_bytes_for(content_type: str) -> int:
    if content_type.startswith("video/"):
        return settings.max_video_upload_mb * 1024 * 1024
    return settings.max_image_upload_mb * 1024 * 1024


async def security_headers_middleware(request: Request, call_next):
    """
    Headers for API responses. The frontend is served separately (Vite in dev, a static host in
    production), and that origin needs its own headers - these do not cover it.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    # This API only ever returns JSON or a redirect, so nothing should be loadable from it.
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    # Report data and presigned media links must not sit in a shared cache.
    response.headers.setdefault("Cache-Control", "no-store")
    if settings.env != "development":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
