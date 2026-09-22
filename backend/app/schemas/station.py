import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.module4_emergency import OffenceCategory
from app.models.station import DiaryEntryType, FirStatus


class StationDirectoryEntry(BaseModel):
    """Public. Where the stations are and how to reach them - no case data of any kind."""

    id: uuid.UUID
    name: str
    code: str
    address: str | None
    lat: float | None
    lng: float | None
    contact_phone: str | None
    sho_name: str | None
    ward_name: str | None
    distance_km: float | None = None


class StationSummary(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    address: str | None
    sho_name: str | None


class DiaryEntryResponse(BaseModel):
    id: uuid.UUID
    entry_date: date
    serial_no: int
    entry_type: DiaryEntryType
    detail: str
    report_id: uuid.UUID | None
    fir_id: uuid.UUID | None
    officer_user_id: uuid.UUID | None
    created_at: datetime

    class Config:
        from_attributes = True


class DiaryNoteRequest(BaseModel):
    detail: str = Field(min_length=3, max_length=2000)


class StationReportRow(BaseModel):
    """A report sitting with this station. Never carries the evidence itself."""

    id: uuid.UUID
    category: OffenceCategory
    geohash: str
    is_restricted: bool
    has_evidence: bool
    acknowledged_at: datetime | None
    closed_at: datetime | None
    closed_without_fir_reason: str | None
    created_at: datetime
    fir_id: uuid.UUID | None
    fir_number: str | None
    hours_since_report: float
    overdue_for_acknowledgement: bool
    overdue_for_fir: bool


class RegisterFirRequest(BaseModel):
    sections: str = Field(min_length=2, max_length=500)
    # A station must register even when the offence is outside its jurisdiction, then transfer.
    is_zero_fir: bool = False


class FirResponse(BaseModel):
    id: uuid.UUID
    fir_number: str
    year: int
    station_id: uuid.UUID
    station_name: str | None = None
    report_id: uuid.UUID
    category: OffenceCategory | None = None
    sections: str
    is_zero_fir: bool
    transferred_to_station_id: uuid.UUID | None
    investigating_officer_id: uuid.UUID | None
    registered_at: datetime
    investigation_deadline: datetime
    status: FirStatus
    chargesheet_filed_at: datetime | None
    court_name: str | None
    closure_reason: str | None
    closed_at: datetime | None
    days_remaining: int


class AssignOfficerRequest(BaseModel):
    investigating_officer_id: uuid.UUID


class TransferRequest(BaseModel):
    to_station_id: uuid.UUID
    reason: str = Field(min_length=3, max_length=500)


class ChargesheetRequest(BaseModel):
    court_name: str = Field(min_length=2, max_length=255)


class ClosureRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class CaseDiaryRequest(BaseModel):
    detail: str = Field(min_length=3, max_length=4000)


class CaseDiaryResponse(BaseModel):
    id: uuid.UUID
    officer_user_id: uuid.UUID
    detail: str
    created_at: datetime

    class Config:
        from_attributes = True
