"""Notification helpers for operational alerts."""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("ahimp.notifications")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def send_anomaly_alert(
    subject: str,
    body: str,
    recipients: list[str] | None = None,
) -> dict:
    """
    Send anomaly alerts using configured channel.

    Behavior:
    - If `ALERT_SMTP_HOST` and recipients exist: send email.
    - Otherwise: log alert to backend logger (non-failing fallback).
    """
    enabled = _env_bool("ANOMALY_ALERTS_ENABLED", default=True)
    if not enabled:
        return {"sent": False, "channel": "disabled", "reason": "ANOMALY_ALERTS_ENABLED=false"}

    to_list = recipients or [x.strip() for x in os.getenv("ANOMALY_ALERT_RECIPIENTS", "").split(",") if x.strip()]
    smtp_host = os.getenv("ALERT_SMTP_HOST", "").strip()

    if smtp_host and to_list:
        smtp_port = int(os.getenv("ALERT_SMTP_PORT", "587"))
        smtp_user = os.getenv("ALERT_SMTP_USER", "").strip()
        smtp_pass = os.getenv("ALERT_SMTP_PASS", "").strip()
        smtp_tls = _env_bool("ALERT_SMTP_TLS", default=True)
        sender = os.getenv("ALERT_EMAIL_FROM", smtp_user or "ahimp-alerts@localhost")

        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = ", ".join(to_list)
        msg["Subject"] = subject
        msg.set_content(body)

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
                if smtp_tls:
                    smtp.starttls()
                if smtp_user and smtp_pass:
                    smtp.login(smtp_user, smtp_pass)
                smtp.send_message(msg)
            return {"sent": True, "channel": "email", "recipients": to_list}
        except Exception as exc:
            logger.exception("Failed sending anomaly email alert")
            return {
                "sent": False,
                "channel": "email",
                "error": str(exc),
                "recipients": to_list,
            }

    logger.warning("ANOMALY ALERT: %s\n%s", subject, body)
    return {"sent": True, "channel": "log", "recipients": to_list}
