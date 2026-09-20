import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.module1_violations import ChallanStatus, IdentityPath, ViolationCaseStatus


class ViolationClassResponse(BaseModel):
    id: uuid.UUID
    slug: str
    label: str
    identity_path: IdentityPath
    statutory_section: str | None

    class Config:
        from_attributes = True


class ViolationCaseResponse(BaseModel):
    id: uuid.UUID
    violation_class_slug: str
    violation_class_label: str
    confidence_score: float | None
    lat: float
    lng: float
    media_id: str
    media_kind: str
    identity_path: IdentityPath
    resolved_plate_number: str | None
    status: ViolationCaseStatus
    source: str
    created_at: datetime


class ViolationStatsResponse(BaseModel):
    """
    Counts only, deliberately. A violation case is an unconfirmed accusation against an
    identifiable person or vehicle, so its evidence, location and any resolved plate stay
    officer-only (spec: names, faces, vehicle numbers and addresses of anyone accused are never
    public, at any stage). What the public gets is whether officers are actually working the
    queue.
    """

    pending_review: int
    confirmed: int
    dismissed: int
    challans_issued: int


class ReclassifyRequest(BaseModel):
    new_violation_class_slug: str


class ChallanResponse(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    statutory_section: str | None
    amount_rupees: int
    due_date: datetime
    status: ChallanStatus

    class Config:
        from_attributes = True


class DisputeRequest(BaseModel):
    reason: str
