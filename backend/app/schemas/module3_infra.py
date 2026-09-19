import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.module3_infra import IssueStatus


class IssueCategoryResponse(BaseModel):
    id: uuid.UUID
    slug: str
    label: str
    sla_hours: int
    escalation_department: str
    escalation_department_tier2: str | None

    class Config:
        from_attributes = True


class IssueCreateResponse(BaseModel):
    """Returned right after a citizen submits a report."""

    id: uuid.UUID
    tracking_token: str
    status: IssueStatus
    sla_deadline: datetime
    merged_into_existing: bool


class IssuePublicResponse(BaseModel):
    id: uuid.UUID
    category_slug: str
    category_label: str
    description: str | None
    lat: float
    lng: float
    status: IssueStatus
    upvote_count: int
    sla_deadline: datetime
    created_at: datetime
    # Opaque object-storage key, fetched via GET /api/media/{media_id}. Safe to expose on a
    # public board: every file has had location metadata stripped at ingestion (photos are also
    # face-blurred; videos are not),
    # and unlike Module 4 evidence they are meant to be publicly visible.
    media_id: str | None = None

    # Public on the Module 3 board so a citizen who lost their code can find their report. This
    # is only safe because the token grants no access here that GET /api/infra/issues/{id}
    # doesn't already give anonymously - it is a lookup handle, not a credential.
    #
    # DO NOT gate any state-changing action on this token (withdrawing a report, editing it,
    # adding follow-up) while it is published, and DO NOT copy this field onto Module 2 or
    # Module 4 responses: there the token IS the reporter's only protected handle, and
    # publishing it would expose whistleblowers.
    tracking_token: str


class IssueStatusHistoryItem(BaseModel):
    status: IssueStatus
    note: str | None
    created_at: datetime


class IssueDetailResponse(IssuePublicResponse):
    history: list[IssueStatusHistoryItem]
    # The proof photo is public on purpose: an officer marking something fixed with no visible
    # evidence is the failure mode the proof requirement exists to prevent.
    resolution_proof_media_id: str | None = None


class IssueResolveRequest(BaseModel):
    note: str | None = None


class ShareableCardResponse(BaseModel):
    """Pre-filled text the citizen can post themselves if an SLA is breached (spec 2.4)."""

    issue_id: uuid.UUID
    share_text: str
    share_url: str
