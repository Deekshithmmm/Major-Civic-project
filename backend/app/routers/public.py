import re

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from app.services.storage import presigned_url

router = APIRouter(prefix="/api/media", tags=["media"])

# Keys this service generates look like "module3/<32 hex>.jpg" or
# "module3/thumbnails/<32 hex>.jpg". Anything else is rejected rather than handed to the storage
# client: the path segment is attacker-controlled, and this keeps it from being used to probe
# for other objects or to smuggle traversal sequences into a key.
_MEDIA_KEY = re.compile(r"^(?:[a-z0-9_]+/){1,3}[0-9a-f]{32}(?:\.(?:jpg|mp4|webm))?$")


@router.get("/{media_id:path}")
def get_media(media_id: str):
    """
    Redirects to a short-lived presigned URL rather than proxying bytes through the API process.

    This only ever reads the general media bucket. Module 4 evidence lives in a separate vault
    bucket that this route has no way to name, and it must stay that way - evidence is reachable
    only through the investigating-officer route that logs the access.
    """
    if not _MEDIA_KEY.fullmatch(media_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    return RedirectResponse(presigned_url(media_id))
