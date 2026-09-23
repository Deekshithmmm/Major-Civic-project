"""
The two clocks of IT Rules 2021 Rule 3(2)(a), and the platform's own compliance against them.

A takedown channel is the one power in this system that lets an official make a citizen's
report disappear. Everything here is built so that using it leaves a mark: a ticket the
complainant can quote, an audit row naming the deciding officer, a reason the anonymous
uploader can read off their tracking token, and a public counter of how often the deadline was
missed. The platform holds itself to the same published-numbers standard it holds a police
station to on the transparency page.
"""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.module2_grievance import Grievance, GrievanceStatus

settings = get_settings()

TICKET_DIGITS = 8


def new_ticket(db: Session) -> str:
    """
    An 8-digit ticket. A complainant quotes this to the Grievance Officer by phone or in a
    letter, so digits beat a random URL-safe string.

    Shorter than a Module 2 tracking token, and deliberately so: that token is a whistleblower's
    only protection and must be unguessable, whereas this ticket unlocks a status, a ground and
    two dates. The complaint text, the complainant's name and their email are never returned by
    ticket lookup, so enumerating tickets harvests nothing.
    """
    for _ in range(10):
        # No leading zero - it gets eaten when the number is retyped or pasted into a spreadsheet.
        ticket = str(secrets.randbelow(9 * 10 ** (TICKET_DIGITS - 1)) + 10 ** (TICKET_DIGITS - 1))
        if not db.execute(select(Grievance.id).where(Grievance.ticket == ticket)).first():
            return ticket
    raise RuntimeError("Could not allocate an unused grievance ticket")


def ack_deadline(received_at: datetime) -> datetime:
    return received_at + timedelta(hours=settings.grievance_ack_hours)


def resolve_deadline(received_at: datetime) -> datetime:
    return received_at + timedelta(days=settings.grievance_resolve_days)


def _aware(value: datetime) -> datetime:
    """Rows written before a timezone-aware default landed can still come back naive."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def is_overdue(grievance: Grievance, now: datetime | None = None) -> bool:
    """Open past the 15-day disposal deadline."""
    if grievance.resolved_at is not None:
        return False
    now = now or datetime.now(timezone.utc)
    return now > resolve_deadline(_aware(grievance.received_at))


def compliance_stats(db: Session) -> dict:
    """
    Published at /api/corruption/compliance, for the same reason the station ledger is
    published: a deadline nobody counts is a deadline nobody keeps. Counts only - no complaint
    ever appears here, because the complainants are named people and the reports they concern
    may have been taken down precisely to stop them being read.
    """
    now = datetime.now(timezone.utc)
    grievances = db.execute(select(Grievance)).scalars().all()

    acknowledged_in_time = 0
    ack_breached = 0
    resolved_in_time = 0
    resolve_breached = 0
    open_overdue = 0

    for g in grievances:
        received = _aware(g.received_at)

        if g.acknowledged_at is None:
            # Still unacknowledged: a breach only once the 24 hours have actually run out.
            if now > ack_deadline(received):
                ack_breached += 1
        elif _aware(g.acknowledged_at) <= ack_deadline(received):
            acknowledged_in_time += 1
        else:
            ack_breached += 1

        if g.resolved_at is not None:
            if _aware(g.resolved_at) <= resolve_deadline(received):
                resolved_in_time += 1
            else:
                resolve_breached += 1
        elif now > resolve_deadline(received):
            open_overdue += 1

    decided = resolved_in_time + resolve_breached
    return {
        "grievances_received": len(grievances),
        "acknowledged_within_deadline": acknowledged_in_time,
        "acknowledgement_deadline_missed": ack_breached,
        "resolved_within_deadline": resolved_in_time,
        "resolution_deadline_missed": resolve_breached,
        "open_past_deadline": open_overdue,
        "upheld": sum(1 for g in grievances if g.status == GrievanceStatus.UPHELD),
        "rejected": sum(1 for g in grievances if g.status == GrievanceStatus.REJECTED),
        # Null rather than 100% when nothing has been decided yet: an empty system should not
        # advertise a perfect record.
        "on_time_resolution_rate": round(resolved_in_time / decided, 3) if decided else None,
        "acknowledgement_deadline_hours": settings.grievance_ack_hours,
        "resolution_deadline_days": settings.grievance_resolve_days,
    }
