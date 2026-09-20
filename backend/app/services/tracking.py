"""Citizen-facing tracking codes for Module 3 reports."""

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.module3_infra import InfrastructureIssue

CODE_DIGITS = 10


def new_tracking_code(db: Session) -> str:
    """
    A 10-digit code. Citizens read these off a screen and type them back in, sometimes over the
    phone, so digits beat a random base64 string.

    Safe to keep short here only because Module 3 codes are printed on the public status board
    anyway - they are a lookup handle, not a credential, and they unlock nothing that
    GET /api/infra/issues/{id} doesn't already return to anyone. Module 2 and Module 4 keep
    high-entropy random tokens: there the token IS the reporter's only protection, and a
    guessable one would let anyone enumerate whistleblower reports.
    """
    for _ in range(10):
        # Never a leading zero: a code that starts with one gets dropped when retyped or pasted
        # into a spreadsheet, and then it no longer matches.
        code = str(secrets.randbelow(9 * 10 ** (CODE_DIGITS - 1)) + 10 ** (CODE_DIGITS - 1))
        taken = db.execute(
            select(InfrastructureIssue.id).where(InfrastructureIssue.tracking_token == code)
        ).first()
        if not taken:
            return code
    raise RuntimeError("Could not allocate an unused tracking code")


def normalise_tracking_code(code: str) -> str:
    """Accept a code typed with the spacing it is displayed in ("4821 903 577")."""
    return "".join(code.split())
