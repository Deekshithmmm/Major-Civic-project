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
    identity_path: IdentityPath
    resolved_plate_number: str | None
    status: ViolationCaseStatus
    source: str
    created_at: datetime


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
