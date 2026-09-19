"""
Shared media ingestion pipeline (spec 2.6): the same stages run for Modules 1-3 so privacy
handling is implemented once and cannot drift between modules.

    photo: virus scan -> EXIF strip -> face detect + blur -> thumbnail -> object storage
    video: virus scan -> metadata strip + audio dropped (stream copy) -> thumbnail -> storage

Videos are deliberately NOT face-blurred. The spec asks for it, but blurring every frame took
25-45s for a 10-second clip, and the product decision was speed. Location metadata is still
stripped from video: that, not the blur, is what keeps a report anonymous, and it costs well
under a second.

Virus scanning is stubbed (no ClamAV wired up in this dev build - see `virus_scan()` below);
everything else is real. Photo face blur uses OpenCV's Haar cascade frontal-face detector, which
is good enough for a demo/hackathon build but is not a production-grade detector - a real
deployment should swap it for a proper model (e.g. a small YOLO-face or RetinaFace) behind this
same function signature.

Module 4 (not implemented here - see models/module4_emergency.py) must NOT reuse this pipeline
as-is: it hashes the original file BEFORE any processing for chain of custody, writes to the
segregated evidence vault, and - since this pipeline no longer blurs video - it needs its own
irreversible blur for sexual-offence footage, which the spec makes mandatory at ingestion.
"""

import io
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image

from app.services.storage import put_object

_thread_local = threading.local()


def _face_cascade() -> cv2.CascadeClassifier:
    # One classifier per thread: uploads run concurrently in FastAPI's threadpool, and sharing a
    # single CascadeClassifier across threads is not documented as safe by OpenCV.
    cascade = getattr(_thread_local, "cascade", None)
    if cascade is None:
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        _thread_local.cascade = cascade
    return cascade

IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
VIDEO_CONTENT_TYPES = {"video/mp4", "video/webm", "video/quicktime"}


@dataclass
class ProcessedMedia:
    media_id: str
    thumbnail_media_id: str | None
    content_type: str


def virus_scan(data: bytes) -> None:
    """
    Stub. A real deployment hooks this to ClamAV (or an equivalent) and raises before any
    further processing on a positive match. Left as a no-op so the pipeline's *shape* matches
    the spec even though the scanner itself isn't wired up.
    """
    return None


def _blur_faces_in_frame(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = _face_cascade().detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
    for (x, y, w, h) in faces:
        # Pad the box slightly so the blur covers hairline/jaw, not just the detector's tight box.
        pad_x, pad_y = int(w * 0.15), int(h * 0.15)
        x0, y0 = max(0, x - pad_x), max(0, y - pad_y)
        x1, y1 = min(frame.shape[1], x + w + pad_x), min(frame.shape[0], y + h + pad_y)
        region = frame[y0:y1, x0:x1]
        if region.size == 0:
            continue
        ksize = max(15, (min(region.shape[:2]) // 2) | 1)  # odd kernel size
        frame[y0:y1, x0:x1] = cv2.GaussianBlur(region, (ksize, ksize), 0)
    return frame


def _strip_and_blur_image(data: bytes) -> tuple[bytes, bytes]:
    """Returns (blurred_full_jpeg_bytes, thumbnail_jpeg_bytes). Drops all EXIF/metadata."""
    image = Image.open(io.BytesIO(data)).convert("RGB")
    frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    frame = _blur_faces_in_frame(frame)
    blurred_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    blurred_image = Image.fromarray(blurred_rgb)  # fresh image object: source EXIF is not carried over

    full_buf = io.BytesIO()
    blurred_image.save(full_buf, format="JPEG", quality=88)

    thumb = blurred_image.copy()
    thumb.thumbnail((320, 320))
    thumb_buf = io.BytesIO()
    thumb.save(thumb_buf, format="JPEG", quality=80)

    return full_buf.getvalue(), thumb_buf.getvalue()


_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# Keep only the first video stream: audio is dropped (a reporter's own voice identifies them) and
# so are data tracks, which on iPhones carry location and device info. Then drop all container,
# stream and chapter metadata - that is where phones put GPS coordinates and make/model.
_STRIP_ARGS = ["-map", "0:v:0", "-map_metadata", "-1", "-map_metadata:s", "-1", "-map_chapters", "-1"]


def _run_ffmpeg(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args],
        capture_output=True,
        text=True,
        timeout=300,
    )


def _strip_video_metadata(data: bytes, content_type: str) -> tuple[bytes, str, bytes]:
    """
    Returns (video_bytes, stored_content_type, thumbnail_jpeg_bytes).

    The video stream is copied, not re-encoded, so this takes well under a second. Faces are
    deliberately NOT blurred (see module docstring). Falls back to an H.264 re-encode only when
    the source codec can't be copied into the output container.
    """
    suffix = {"video/webm": ".webm", "video/quicktime": ".mov"}.get(content_type, ".mp4")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"in{suffix}"
        src.write_bytes(data)

        if content_type == "video/webm":
            out, out_type, copy_args = Path(tmp) / "out.webm", "video/webm", ["-c:v", "copy"]
        else:
            out, out_type = Path(tmp) / "out.mp4", "video/mp4"
            copy_args = ["-c:v", "copy", "-movflags", "+faststart"]

        result = _run_ffmpeg("-i", str(src), *_STRIP_ARGS, *copy_args, str(out))
        if result.returncode != 0:
            out, out_type = Path(tmp) / "reencoded.mp4", "video/mp4"
            result = _run_ffmpeg(
                "-i", str(src), *_STRIP_ARGS,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(out),
            )
            if result.returncode != 0:
                raise ValueError(f"Could not process video: {result.stderr.strip()[-300:]}")

        thumb = Path(tmp) / "thumb.jpg"
        _run_ffmpeg(
            "-i", str(out), "-frames:v", "1",
            "-vf", "scale=320:320:force_original_aspect_ratio=decrease", "-q:v", "5", str(thumb),
        )
        return out.read_bytes(), out_type, (thumb.read_bytes() if thumb.exists() else b"")


def process_and_store(data: bytes, content_type: str, key_prefix: str = "media") -> ProcessedMedia:
    """
    Runs the shared pipeline and returns opaque media IDs for the processed file + thumbnail.

    Blocking: ~2s for a browser-compressed photo (face detection), well under a second for a
    video (stream copy, no blur), longer only if a video's codec forces a re-encode. Call it only
    from plain `def` endpoints, which FastAPI runs in a worker thread. From an `async def`
    endpoint it stalls the event loop and freezes every other request until it returns.
    """
    virus_scan(data)

    if content_type in IMAGE_CONTENT_TYPES:
        processed, thumbnail = _strip_and_blur_image(data)
        stored_type = "image/jpeg"
    elif content_type in VIDEO_CONTENT_TYPES:
        processed, stored_type, thumbnail = _strip_video_metadata(data, content_type)
    else:
        raise ValueError(f"Unsupported content type for media pipeline: {content_type}")

    media_id = put_object(processed, stored_type, key_prefix=key_prefix)

    thumbnail_media_id = None
    if thumbnail:
        thumbnail_media_id = put_object(thumbnail, "image/jpeg", key_prefix=f"{key_prefix}/thumbnails")

    return ProcessedMedia(media_id=media_id, thumbnail_media_id=thumbnail_media_id, content_type=stored_type)
