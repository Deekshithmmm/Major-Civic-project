"""
Police station procedures: the General Diary, the FIR register and the case diary.

Modelled on how an Indian police station actually records work, because the transparency layer
in Module 4 is only meaningful if the station-side record it measures is the real one:

  - **General Diary** (Roznamcha, Police Act s.44): every event at the station is entered in
    sequence, numbered per station per day. Real GDs are bound registers - entries are added,
    never altered - so `station_diary_entries` is append-only at the database level.
  - **FIR** (BNSS s.173, formerly CrPC s.154): registration is mandatory where the information
    discloses a cognizable offence (*Lalita Kumari v. Govt of U.P.*, 2014). The number is issued
    by the station, in sequence, per year.
  - **Zero FIR**: a station must register an FIR even when the offence falls outside its
    jurisdiction, then transfer it to the right station. Refusing on jurisdiction grounds is the
    exact failure the practice exists to prevent, so transfer is modelled as a procedure rather
    than a reason to decline.
  - **Case diary** (BNSS s.192, formerly CrPC s.172): the investigating officer's day-by-day
    record. Also append-only.

`PoliceStation` itself lives in models/module4_emergency.py, where reports are routed to it.

Personal data: officer user IDs and free-text entries written by officers. No citizen identifier
is stored - the reports these hang off are anonymous. Retention: tied to the case, same schedule
as the evidence it concerns.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class DiaryEntryType(str, enum.Enum):
    COMPLAINT_RECEIVED = "complaint_received"
    ACKNOWLEDGED = "acknowledged"
    NCR_REGISTERED = "ncr_registered"
    FIR_REGISTERED = "fir_registered"
    IO_ASSIGNED = "io_assigned"
    ZERO_FIR_TRANSFERRED_OUT = "zero_fir_transferred_out"
    TRANSFERRED_IN = "transferred_in"
    CASE_DIARY = "case_diary"
    CHARGESHEET_FILED = "chargesheet_filed"
    CLOSED_WITHOUT_FIR = "closed_without_fir"
    CASE_CLOSED = "case_closed"
    NOTE = "note"


class StationDiaryEntry(Base):
    """
    One line of the station's General Diary. Append-only at the database level (migration
    adds the same reject_mutation trigger the audit log uses): a diary that can be rewritten
    after the fact cannot evidence when a station learned something.
    """

    __tablename__ = "station_diary_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("police_stations.id"), nullable=False, index=True
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    serial_no: Mapped[int] = mapped_column(Integer, nullable=False)  # restarts each day, per station

    entry_type: Mapped[DiaryEntryType] = mapped_column(Enum(DiaryEntryType, name="diary_entry_type"), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)

    report_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    fir_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    officer_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("station_id", "entry_date", "serial_no", name="uq_gd_serial_per_station_day"),)


class FirStatus(str, enum.Enum):
    UNDER_INVESTIGATION = "under_investigation"
    TRANSFERRED = "transferred"
    CHARGESHEET_FILED = "chargesheet_filed"
    CLOSED = "closed"


class FirRecord(Base):
    """
    The authoritative FIR. Module 4's public ledger counts these - a report is "converted" when
    an FIR exists for it, never because a field was typed somewhere.
    """

    __tablename__ = "fir_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("police_stations.id"), nullable=False, index=True
    )
    # Station-issued, sequential per year: "0042/2026".
    fir_number: Mapped[str] = mapped_column(String(32), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emergency_reports.id"), unique=True, nullable=False
    )
    sections: Mapped[str] = mapped_column(String(500), nullable=False)  # e.g. "BNS 103, 3(5)"

    # Registered despite the offence falling outside this station's jurisdiction, pending
    # transfer to the right one. The registration still counts; only the investigation moves.
    is_zero_fir: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    transferred_to_station_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("police_stations.id"), nullable=True
    )

    registered_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    investigating_officer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # When the investigation is expected to conclude. Surfaced to the station and counted by the
    # public ledger; see services/station.py for how the window is chosen.
    investigation_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[FirStatus] = mapped_column(
        Enum(FirStatus, name="fir_status"), default=FirStatus.UNDER_INVESTIGATION, nullable=False
    )
    chargesheet_filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    court_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    closure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("station_id", "fir_number", name="uq_fir_number_per_station"),)


class CaseDiaryEntry(Base):
    """The investigating officer's running record (BNSS s.192). Append-only."""

    __tablename__ = "case_diary_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fir_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fir_records.id"), nullable=False, index=True
    )
    officer_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
