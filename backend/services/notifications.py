"""Notification helpers for operational alerts."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import logging
import os
import smtplib
from email.message import EmailMessage

import httpx

logger = logging.getLogger("ahimp.notifications")
_ALERT_BUFFER: deque[dict] = deque(maxlen=500)


def _split_csv_env(name: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, "").split(",") if x.strip()]


def _record_alert(payload: dict) -> int:
    alert_id = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    payload = {
        "alert_id": alert_id,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        **payload,
    }
    _ALERT_BUFFER.appendleft(payload)
    return alert_id


def get_recent_alerts(limit: int = 50, severity: str | None = None) -> list[dict]:
    """Return recent alert events for dashboard consumption."""
    items = list(_ALERT_BUFFER)
    if severity:
        sev = severity.upper()
        items = [row for row in items if str(row.get("severity", "")).upper() == sev]
    return items[:limit]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def send_anomaly_alert(
    subject: str,
    body: str,
    recipients: list[str] | None = None,
    severity: str = "RED",
) -> dict:
    """
    Send anomaly alerts using configured channel.

    Behavior:
    - If `ALERT_SMTP_HOST` and recipients exist: send email.
    - Otherwise: log alert to backend logger (non-failing fallback).
    """
    enabled = _env_bool("ANOMALY_ALERTS_ENABLED", default=True)
    if not enabled:
        alert_id = _record_alert(
            {
                "subject": subject,
                "severity": severity,
                "channels": [],
                "status": "disabled",
            }
        )
        return {
            "sent": False,
            "channels": [],
            "reason": "ANOMALY_ALERTS_ENABLED=false",
            "alert_id": alert_id,
        }

    to_list = recipients or _split_csv_env("ANOMALY_ALERT_RECIPIENTS")
    sms_list = _split_csv_env("ANOMALY_ALERT_SMS_RECIPIENTS")
    smtp_host = os.getenv("ALERT_SMTP_HOST", "").strip()
    sms_webhook_url = os.getenv("ALERT_SMS_WEBHOOK_URL", "").strip()

    channels: list[str] = []
    email_result: dict = {"sent": False}
    sms_result: dict = {"sent": False}

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
            channels.append("email")
            email_result = {"sent": True, "recipients": to_list}
        except Exception as exc:
            logger.exception("Failed sending anomaly email alert")
            email_result = {
                "sent": False,
                "error": str(exc),
                "recipients": to_list,
            }

    if sms_webhook_url and sms_list:
        payload = {
            "to": sms_list,
            "subject": subject,
            "message": body,
            "severity": severity,
        }
        try:
            response = httpx.post(sms_webhook_url, json=payload, timeout=10.0)
            if response.status_code < 400:
                channels.append("sms")
                sms_result = {"sent": True, "recipients": sms_list}
            else:
                sms_result = {
                    "sent": False,
                    "status_code": response.status_code,
                    "body": response.text[:200],
                }
        except Exception as exc:
            logger.exception("Failed sending anomaly SMS alert")
            sms_result = {
                "sent": False,
                "error": str(exc),
                "recipients": sms_list,
            }

    if not channels:
        channels.append("log")
        logger.warning("ANOMALY ALERT: %s\n%s", subject, body)

    alert_id = _record_alert(
        {
            "subject": subject,
            "severity": severity,
            "channels": channels,
            "email": email_result,
            "sms": sms_result,
        }
    )

    return {
        "sent": bool(channels),
        "channels": channels,
        "email": email_result,
        "sms": sms_result,
        "alert_id": alert_id,
    }
