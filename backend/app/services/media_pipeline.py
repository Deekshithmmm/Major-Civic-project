"""
Shared media ingestion pipeline (spec 2.6): the same stages run for Modules 1-3 so privacy
handling is implemented once and cannot drift between modules.

    upload -> virus scan -> metadata/EXIF strip -> face detect + blur (irreversible on the
    stored copy) -> thumbnail extraction -> write to object storage -> return opaque media ID

Virus scanning is stubbed (no ClamAV wired up in this dev build - see `virus_scan()` below);
everything else is real. Face blur uses OpenCV's Haar cascade frontal-face detector, which is
good enough for a demo/hackathon build but is not a production-grade detector - a real
deployment should swap it for a proper model (e.g. a small YOLO-face or RetinaFace) behind this
same function signature.

Module 4 (not implemented here - see models/module4_emergency.py) differs in two ways this
module does NOT do: it hashes the original file BEFORE any processing for chain of custody, and
it writes to the segregated evidence vault bucket instead of general media storage.
"""

import io
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from app.services.storage import put_object

_FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

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
    faces = _FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
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


def _strip_and_blur_video(data: bytes) -> tuple[bytes, bytes]:
    """Returns (blurred_mp4_bytes, thumbnail_jpeg_bytes) using an OpenCV frame-by-frame pass."""
    with tempfile.TemporaryDirectory() as tmp:
        in_path = Path(tmp) / "in.mp4"
        out_path = Path(tmp) / "out.mp4"
        in_path.write_bytes(data)

        cap = cv2.VideoCapture(str(in_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 24
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))

        thumbnail_bytes = None
        frame_index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = _blur_faces_in_frame(frame)
            writer.write(frame)
            if frame_index == 0:
                ok_thumb, jpeg = cv2.imencode(".jpg", frame)
                if ok_thumb:
                    thumbnail_bytes = jpeg.tobytes()
            frame_index += 1

        cap.release()
        writer.release()

        blurred_bytes = out_path.read_bytes()
        return blurred_bytes, (thumbnail_bytes or b"")


def process_and_store(data: bytes, content_type: str, key_prefix: str = "media") -> ProcessedMedia:
    """Runs the shared pipeline and returns opaque media IDs for the processed file + thumbnail."""
    virus_scan(data)

    if content_type in IMAGE_CONTENT_TYPES:
        processed, thumbnail = _strip_and_blur_image(data)
        media_id = put_object(processed, "image/jpeg", key_prefix=key_prefix)
    elif content_type in VIDEO_CONTENT_TYPES:
        processed, thumbnail = _strip_and_blur_video(data)
        media_id = put_object(processed, "video/mp4", key_prefix=key_prefix)
    else:
        raise ValueError(f"Unsupported content type for media pipeline: {content_type}")

    thumbnail_media_id = None
    if thumbnail:
        thumbnail_media_id = put_object(thumbnail, "image/jpeg", key_prefix=f"{key_prefix}/thumbnails")

    return ProcessedMedia(media_id=media_id, thumbnail_media_id=thumbnail_media_id, content_type=content_type)
