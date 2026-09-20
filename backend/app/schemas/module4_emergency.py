import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.module4_emergency import OffenceCategory


class EmergencyRoutingRuleResponse(BaseModel):
    category: OffenceCategory
    alert_routed_to: str
    has_public_record: bool
    is_hard_stop: bool

    class Config:
        from_attributes = True


class SupportResource(BaseModel):
    label: str
    number: str


class ReportCreateResponse(BaseModel):
    """
    Returned to the reporter. Carries no report ID a third party could use, only the tracking
    token, plus the support resources the spec requires be surfaced immediately on submission.
    """

    tracking_token: str
    category: OffenceCategory
    is_restricted: bool
    routed_to: str
    station_name: str | None
    evidence_sealed: bool
    evidence_sha256: str | None
    support_resources: list[SupportResource]


class HardStopResponse(BaseModel):
    """Not an error page - the one response where refusing is the correct product behaviour."""

    message: str
    redirect_to: list[SupportResource]


class ReportStatusResponse(BaseModel):
    tracking_token: str
    category: OffenceCategory
    status: str
    acknowledged_at: datetime | None
    fir_number: str | None
    created_at: datetime


class StationReportResponse(BaseModel):
    """Investigating-officer view. Never includes a link to the evidence itself."""

    id: uuid.UUID
    category: OffenceCategory
    geohash: str
    is_restricted: bool
    has_evidence: bool
    acknowledged_at: datetime | None
    fir_number: str | None
    fir_registered_at: datetime | None
    closed_at: datetime | None
    closed_without_fir_reason: str | None
    created_at: datetime


class EvidenceAccessRequest(BaseModel):
    case_or_fir_number: str


class EvidenceAccessResponse(BaseModel):
    url: str
    expires_seconds: int
    original_sha256: str | None
    chain_of_custody_entries: int


class FirRequest(BaseModel):
    fir_number: str


class CloseRequest(BaseModel):
    reason: str


class ChainOfCustodyItem(BaseModel):
    action: str
    detail: str | None
    officer_user_id: uuid.UUID | None
    case_or_fir_number: str | None
    accessed_at: datetime


class StationLedgerResponse(BaseModel):
    station_id: str
    station_name: str
    station_code: str
    reports_30d: int
    reports_90d: int
    unacknowledged_past_sla: int
    firs_registered: int
    fir_conversion_rate: float | None
    median_ack_hours: float | None
    open_past_fir_sla: int
    closed_without_fir: int
    flagged_red: bool


class HotspotCellResponse(BaseModel):
    ward_name: str
    quarter: str
    category: str
    report_count: int
    firs_registered: int
