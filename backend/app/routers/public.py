from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.services.storage import presigned_url

router = APIRouter(prefix="/api/media", tags=["media"])


@router.get("/{media_id:path}")
def get_media(media_id: str):
    """
    Redirects to a short-lived presigned URL rather than proxying bytes through the API
    process. Evidence-vault media (Module 4) must never be reachable through this route - only
    the general media bucket - once Module 4 is implemented.
    """
    url = presigned_url(media_id)
    return RedirectResponse(url)
