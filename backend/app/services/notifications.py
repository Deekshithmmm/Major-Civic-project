"""
Notification gateway abstraction (spec 2.1: "Abstract it so the provider is swappable"). Local
dev uses the "console" provider, which just logs - no real SMS/email provider credentials are
required to demonstrate the full flow end to end (spec's framing requirement).
"""

import logging

from app.config import get_settings

logger = logging.getLogger("civic.notifications")
settings = get_settings()


def send_email(to: str, subject: str, body: str) -> None:
    if settings.notification_provider == "console":
        logger.info("EMAIL -> %s | %s\n%s", to, subject, body)
        return
    raise NotImplementedError(f"Email provider '{settings.notification_provider}' not wired up in this build")


def send_sms(to: str, body: str) -> None:
    if settings.notification_provider == "console":
        logger.info("SMS -> %s | %s", to, body)
        return
    raise NotImplementedError(f"SMS provider '{settings.notification_provider}' not wired up in this build")
