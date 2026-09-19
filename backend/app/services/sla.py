"""SLA deadline calculation and breach detection for Module 3 (spec 2.4, step 5)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.module3_infra import InfrastructureIssue, IssueStatus


def compute_sla_deadline(sla_hours: int, from_time: datetime | None = None) -> datetime:
    from_time = from_time or datetime.now(timezone.utc)
    return from_time + timedelta(hours=sla_hours)


def mark_overdue_issues(db: Session) -> int:
    """
    Sweep open issues past their SLA deadline and flip them to OVERDUE so the public board goes
    red (spec 2.4: "On breach, the issue auto-escalates ... and turns red on the public board").
    Intended to run on a periodic job (e.g. a Celery beat task); exposed here as a plain
    function so it can also be called from a debug endpoint or a cron-less scheduler for now.
    """
    now = datetime.now(timezone.utc)
    stmt = select(InfrastructureIssue).where(
        InfrastructureIssue.status.in_([IssueStatus.REPORTED, IssueStatus.ACKNOWLEDGED, IssueStatus.IN_PROGRESS]),
        InfrastructureIssue.sla_deadline < now,
    )
    overdue = db.execute(stmt).scalars().all()
    for issue in overdue:
        issue.status = IssueStatus.OVERDUE
    db.commit()
    return len(overdue)
