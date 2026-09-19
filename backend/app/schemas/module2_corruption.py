import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.module2_corruption import AccusedPartyType, ModerationStatus, PublicStatusBadge


class RoutingRuleResponse(BaseModel):
    accused_party_type: AccusedPartyType
    primary_route_body: str
    notify_local_police: bool

    class Config:
        from_attributes = True


class ReportCreateResponse(BaseModel):
    tracking_token: str
    moderation_status: ModerationStatus


class ReportStatusResponse(BaseModel):
    tracking_token: str
    moderation_status: ModerationStatus
    public_status_badge: PublicStatusBadge
    created_at: datetime


class FeedItemResponse(BaseModel):
    id: uuid.UUID
    accused_department: str
    accused_designation: str
    description: str | None
    geohash: str
    public_status_badge: PublicStatusBadge
    created_at: datetime

    class Config:
        from_attributes = True


class ModerationDecisionRequest(BaseModel):
    reason: str | None = None
