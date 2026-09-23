"""
The complaint channel the IT Rules 2021 require of an intermediary that publishes
user-submitted accusations, plus the right of reply the spec promises alongside it
(docs/spec-summary.md: "Moderated feed, status badges, right of reply").

Rule 3(2)(a) of the Intermediary Guidelines obliges an intermediary to publish the name and
contact of a Grievance Officer, acknowledge a complaint within 24 hours, and dispose of it
within 15 days. Those two clocks are columns here rather than prose in a policy page, because
the platform publishes its own compliance against them on the same terms it publishes a police
station's (see services/grievance.py).

Personal data, and why it exists here when it exists nowhere else in Module 2:
  - `Grievance` holds a named complainant's name and email. A grievance cannot be disposed of
    without a way to write back to the person who raised it, and the Rules require exactly that
    reply. This is the one place in Module 2 where a real identity is stored, and it belongs to
    the person objecting to a report - never to the person who filed one.
  - `RightOfReply` holds the responding official's name and work email for verification. Only
    the department and designation are ever published; see the column comments.
  - Neither table gets an IP column, for the same reason CorruptionReport has none.

Retention: both are kept for the life of the report they concern plus the audit trail, since a
takedown decision has to stay reviewable. A production deployment should purge
`complainant_email` and `author_contact_email` once the matter is closed and the appeal window
has passed - that is a scheduled job this build does not ship.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base, UTCDateTime


class GrievanceGround(str, enum.Enum):
    """
    Why the complainant says the content should come down. Kept as an enum so the compliance
    figures can show *what* is being complained about, not just how much - a spike in
    IDENTIFIES_PRIVATE_PERSON means the blur pipeline is failing, which is a different problem
    from a spike in FACTUALLY_INCORRECT.
    """

    FACTUALLY_INCORRECT = "factually_incorrect"
    IDENTIFIES_PRIVATE_PERSON = "identifies_private_person"
    DEFAMATORY = "defamatory"
    SUB_JUDICE = "sub_judice"
    NOT_MY_DEPARTMENT = "not_my_department"
    OTHER = "other"


class GrievanceStatus(str, enum.Enum):
    RECEIVED = "received"
    ACKNOWLEDGED = "acknowledged"
    UPHELD = "upheld"  # content taken down
    REJECTED = "rejected"  # content stays up


class Grievance(Base):
    __tablename__ = "content_grievances"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Numeric, because a complainant reads it back over the phone to the Grievance Officer. It is
    # safe for it to be short only because the tracking endpoint returns status and dates and
    # nothing else - guessing a ticket reveals no name, no email and no complaint text.
    ticket: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)

    report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("corruption_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )

    ground: Mapped[GrievanceGround] = mapped_column(Enum(GrievanceGround, name="grievance_ground"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    complainant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    complainant_email: Mapped[str] = mapped_column(String(320), nullable=False)
    # Self-declared and unverified: "Deputy Commissioner, Revenue". Recorded because it changes
    # how a complaint is weighed, never displayed as though the platform had confirmed it.
    complainant_designation: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[GrievanceStatus] = mapped_column(
        Enum(GrievanceStatus, name="grievance_status"), default=GrievanceStatus.RECEIVED, nullable=False
    )

    received_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now(), nullable=False)
    # Set when the automatic acknowledgement actually goes out, not when the row is written. If
    # the mail gateway is down this stays null and the 24-hour duty is visibly in breach, which
    # is the honest outcome.
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


class ReplyStatus(str, enum.Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"


class RightOfReply(Base):
    """
    A response from the body an allegation concerns, published under the allegation itself.

    The reply is institutional, never personal. `author_name` and `author_contact_email` exist
    so a moderator can verify that the reply really came from that office; only
    `author_department`, `author_designation` and `body` are ever published. That is not
    squeamishness - Module 2 never names the accused individual, and publishing the name of the
    officer who replies to an allegation about a single-post designation would name them by the
    back door.

    Replies are moderated before publication for the obvious reason: an unmoderated one is a
    free channel for anyone at all to post a fake official denial.
    """

    __tablename__ = "right_of_reply"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("corruption_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )

    body: Mapped[str] = mapped_column(Text, nullable=False)

    author_department: Mapped[str] = mapped_column(String(255), nullable=False)  # published
    author_designation: Mapped[str] = mapped_column(String(255), nullable=False)  # published
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)  # never published
    author_contact_email: Mapped[str] = mapped_column(String(320), nullable=False)  # never published

    status: Mapped[ReplyStatus] = mapped_column(
        Enum(ReplyStatus, name="reply_status"), default=ReplyStatus.PENDING, nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now(), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
