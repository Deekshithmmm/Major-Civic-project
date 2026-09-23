"""
Request and response shapes for the grievance and right-of-reply channel.

The response models are where the publication rules are actually enforced: `ReplyPublic` has no
field for the responding official's name or email, and `GrievanceTicketResponse` has no field
for the complaint text or the complainant. A future edit that starts leaking either has to add
a field here first, which is a visible thing to do in review.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.module2_grievance import GrievanceGround, GrievanceStatus, ReplyStatus


class GrievanceOfficerResponse(BaseModel):
    """Rule 3(2)(a) publication duty: who to write to, and by when they must answer."""

    name: str
    designation: str
    email: str
    address: str
    acknowledgement_deadline_hours: int
    resolution_deadline_days: int


class GrievanceCreateRequest(BaseModel):
    report_id: uuid.UUID
    ground: GrievanceGround
    body: str = Field(min_length=20, max_length=5000)
    complainant_name: str = Field(min_length=2, max_length=255)
    complainant_email: EmailStr
    complainant_designation: str | None = Field(default=None, max_length=255)


class GrievanceCreateResponse(BaseModel):
    ticket: str
    status: GrievanceStatus
    acknowledged: bool
    resolution_due_by: datetime


class GrievanceTicketResponse(BaseModel):
    """
    What anyone holding a ticket may read. Status and dates only: no complaint text, no
    complainant, no report contents.
    """

    ticket: str
    status: GrievanceStatus
    ground: GrievanceGround
    received_at: datetime
    acknowledged_at: datetime | None
    resolution_due_by: datetime
    resolved_at: datetime | None
    resolution_note: str | None
    overdue: bool


class GrievanceQueueItem(BaseModel):
    """Moderator-side view. This is the only shape that carries the complainant's identity."""

    id: uuid.UUID
    ticket: str
    report_id: uuid.UUID
    ground: GrievanceGround
    body: str
    complainant_name: str
    complainant_email: str
    complainant_designation: str | None
    status: GrievanceStatus
    received_at: datetime
    acknowledged_at: datetime | None
    resolution_due_by: datetime
    overdue: bool
    report_department: str
    report_designation: str
    report_taken_down: bool

    class Config:
        from_attributes = True


class GrievanceDecisionRequest(BaseModel):
    uphold: bool
    # Required in both directions. A takedown with no stated reason is unreviewable, and so is a
    # refusal - the complainant is entitled to be told why under the same rule that gave them
    # the channel.
    note: str = Field(min_length=10, max_length=5000)


class ReplyCreateRequest(BaseModel):
    report_id: uuid.UUID
    body: str = Field(min_length=20, max_length=5000)
    author_department: str = Field(min_length=2, max_length=255)
    author_designation: str = Field(min_length=2, max_length=255)
    author_name: str = Field(min_length=2, max_length=255)
    author_contact_email: EmailStr


class ReplyCreateResponse(BaseModel):
    id: uuid.UUID
    status: ReplyStatus


class ReplyPublic(BaseModel):
    """Published under the allegation. Institutional attribution only, by design."""

    id: uuid.UUID
    body: str
    author_department: str
    author_designation: str
    published_at: datetime | None


class ReplyQueueItem(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    body: str
    author_department: str
    author_designation: str
    author_name: str
    author_contact_email: str
    status: ReplyStatus
    submitted_at: datetime
    report_department: str
    report_designation: str


class ReplyDecisionRequest(BaseModel):
    publish: bool
    note: str | None = Field(default=None, max_length=2000)


class ComplianceResponse(BaseModel):
    grievances_received: int
    acknowledged_within_deadline: int
    acknowledgement_deadline_missed: int
    resolved_within_deadline: int
    resolution_deadline_missed: int
    open_past_deadline: int
    upheld: int
    rejected: int
    on_time_resolution_rate: float | None
    acknowledgement_deadline_hours: int
    resolution_deadline_days: int
