"""Validation and quarantine workflow for ingestion records."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from statistics import mean, pstdev
from typing import Any

from sqlalchemy.orm import Session

from database.models import (
    ConsumptionRecord,
    ConsumptionRecordAudit,
    Department,
    Item,
)
from services.notifications import send_anomaly_alert


MAX_QTY = 100000
MAX_LOOKBACK_DAYS = 90


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)).date()
    except Exception:
        return None


def _record_exists(db: Session, item_id: int, usage_date: date, department_id: int) -> bool:
    row = (
        db.query(ConsumptionRecord.consumption_id)
        .filter(
            ConsumptionRecord.item_id == item_id,
            ConsumptionRecord.usage_date == usage_date,
            ConsumptionRecord.department_id == department_id,
        )
        .first()
    )
    return row is not None


def _score_anomaly(db: Session, item_id: int, quantity_used: int) -> tuple[float, str | None]:
    rows = (
        db.query(ConsumptionRecord.quantity_used)
        .filter(
            ConsumptionRecord.item_id == item_id,
            ConsumptionRecord.quantity_used.isnot(None),
        )
        .all()
    )
    if len(rows) < 2:
        return 0.0, None

    values = [float(row[0]) for row in rows if row[0] is not None]
    if len(values) < 2:
        return 0.0, None

    mean_val = float(mean(values))
    std_val = float(pstdev(values))
    if std_val <= 1e-9:
        return 0.0, None

    z_score = abs((float(quantity_used) - mean_val) / std_val)
    if z_score > 3.0:
        return z_score, "RED"
    if z_score > 2.0:
        return z_score, "YELLOW"
    return z_score, None


def validate_candidate_records(db: Session, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate incoming records against schema, ranges, refs, and duplicates."""
    valid_records: list[dict[str, Any]] = []
    invalid_rows: list[dict[str, Any]] = []

    min_date = datetime.now(tz=timezone.utc).date() - timedelta(days=MAX_LOOKBACK_DAYS)
    max_date = datetime.now(tz=timezone.utc).date()
    seen_keys: set[tuple[int, date, int]] = set()

    for idx, raw in enumerate(records):
        row = dict(raw)
        errors: list[str] = []

        item_id = _to_int(row.get("item_id"))
        quantity_used = _to_int(row.get("quantity_used"))
        usage_date = _to_date(row.get("usage_date"))
        department_id = _to_int(row.get("department_id")) or 1
        patient_type = str(row.get("patient_type") or "general").strip().lower() or "general"
        batch_id = _to_int(row.get("batch_id"))

        if item_id is None:
            errors.append("missing_item_id")
        if quantity_used is None:
            errors.append("missing_quantity_used")
        if usage_date is None:
            errors.append("missing_usage_date")
        if department_id is None:
            errors.append("missing_department_id")

        if quantity_used is not None and not (0 <= quantity_used <= MAX_QTY):
            errors.append("invalid_quantity_range")
        if usage_date is not None and not (min_date <= usage_date <= max_date):
            errors.append("invalid_usage_date_range")

        if item_id is not None:
            item_exists = db.query(Item.item_id).filter(Item.item_id == item_id).first() is not None
            if not item_exists:
                errors.append("invalid_item_id")

        if department_id is not None:
            dept_exists = (
                db.query(Department.department_id)
                .filter(Department.department_id == department_id)
                .first()
                is not None
            )
            if not dept_exists:
                errors.append("invalid_department_id")

        if item_id is not None and usage_date is not None and department_id is not None:
            key = (item_id, usage_date, department_id)
            if key in seen_keys:
                errors.append("duplicate_in_payload")
            seen_keys.add(key)

            if _record_exists(db, item_id, usage_date, department_id):
                errors.append("duplicate_in_database")

        if errors:
            invalid_rows.append(
                {
                    "index": idx,
                    "errors": errors,
                    "row": row,
                }
            )
            continue

        valid_records.append(
            {
                "item_id": item_id,
                "quantity_used": quantity_used,
                "usage_date": usage_date,
                "department_id": department_id,
                "patient_type": patient_type,
                "batch_id": batch_id,
            }
        )

    return {
        "valid_records": valid_records,
        "invalid_rows": invalid_rows,
    }


def record_quarantine_issues(
    db: Session,
    invalid_rows: list[dict[str, Any]],
    anomaly_rows: list[dict[str, Any]],
    source: str = "ingestion_agent",
) -> dict[str, Any]:
    """Persist suspicious ingestion rows into quarantine/audit table."""
    created_ids: list[int] = []
    red = yellow = 0

    for entry in invalid_rows:
        row = entry.get("row", {})
        reason = ",".join(entry.get("errors", [])) or "validation_error"
        audit = ConsumptionRecordAudit(
            item_id=_to_int(row.get("item_id")),
            department_id=_to_int(row.get("department_id")),
            quantity_used=_to_int(row.get("quantity_used")),
            usage_date=_to_date(row.get("usage_date")),
            z_score=None,
            severity="RED",
            reason=reason,
            status="PENDING",
            source=source,
            raw_payload=json.dumps(row, default=str),
        )
        db.add(audit)
        db.flush()
        created_ids.append(int(audit.audit_id))
        red += 1

    for row in anomaly_rows:
        sev = str(row.get("severity") or "YELLOW").upper()
        z_val = float(row.get("z_score") or 0.0)
        if sev == "RED":
            red += 1
        elif sev == "YELLOW":
            yellow += 1

        audit = ConsumptionRecordAudit(
            item_id=_to_int(row.get("item_id")),
            department_id=_to_int(row.get("department_id")),
            quantity_used=_to_int(row.get("quantity_used")),
            usage_date=_to_date(row.get("usage_date")),
            z_score=z_val,
            severity=sev,
            reason="anomaly_detected",
            status="PENDING" if sev == "RED" else "FLAGGED",
            source=source,
            raw_payload=json.dumps(row, default=str),
        )
        db.add(audit)
        db.flush()
        created_ids.append(int(audit.audit_id))

    db.commit()
    alert: dict[str, Any] = {
        "sent": False,
        "channels": [],
        "reason": "none",
    }
    if red > 0 or yellow > 0:
        body = (
            f"Quarantine records created: {len(created_ids)}\n"
            f"RED: {red}\n"
            f"YELLOW: {yellow}\n"
            f"Source: {source}"
        )
        severity = "RED" if red > 0 else "YELLOW"
        alert = send_anomaly_alert(
            subject="AHIMP Quarantine Review Required",
            body=body,
            severity=severity,
        )

    return {
        "created_ids": created_ids,
        "red": red,
        "yellow": yellow,
        "alert": alert,
    }


def list_audit_records(
    db: Session,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    query = db.query(ConsumptionRecordAudit)
    if status:
        query = query.filter(ConsumptionRecordAudit.status == status.upper())

    rows = (
        query.order_by(ConsumptionRecordAudit.created_at.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 500)))
        .all()
    )

    output: list[dict[str, Any]] = []
    for row in rows:
        output.append(
            {
                "audit_id": int(row.audit_id),
                "item_id": row.item_id,
                "department_id": row.department_id,
                "quantity_used": row.quantity_used,
                "usage_date": str(row.usage_date) if row.usage_date else None,
                "z_score": float(row.z_score) if row.z_score is not None else None,
                "severity": row.severity,
                "reason": row.reason,
                "status": row.status,
                "source": row.source,
                "reviewed_by": row.reviewed_by,
                "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return output


def review_audit_record(
    db: Session,
    audit_id: int,
    action: str,
    reviewed_by: str,
    comment: str | None = None,
    create_consumption_record: bool = False,
) -> dict[str, Any]:
    row = db.query(ConsumptionRecordAudit).filter(ConsumptionRecordAudit.audit_id == audit_id).first()
    if row is None:
        raise ValueError("Audit record not found")

    normalized_action = action.strip().lower()
    if normalized_action not in {"approve", "reject"}:
        raise ValueError("Action must be 'approve' or 'reject'")

    row.reviewed_by = reviewed_by
    row.reviewed_at = datetime.now(tz=timezone.utc)
    if normalized_action == "approve":
        row.status = "APPROVED"
        if create_consumption_record and row.item_id and row.department_id and row.quantity_used and row.usage_date:
            db.add(
                ConsumptionRecord(
                    item_id=int(row.item_id),
                    department_id=int(row.department_id),
                    quantity_used=int(row.quantity_used),
                    usage_date=row.usage_date,
                    patient_type="general",
                    batch_id=None,
                )
            )
    else:
        row.status = "REJECTED"

    if comment:
        row.reason = f"{row.reason};review:{comment}"[:255]

    db.commit()

    return {
        "audit_id": int(row.audit_id),
        "status": row.status,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
    }


def assess_records_for_quarantine(db: Session, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Validation + anomaly assessment helper for admin and agent workflows."""
    validation = validate_candidate_records(db, records)
    valid_records = validation["valid_records"]
    invalid_rows = validation["invalid_rows"]

    anomaly_rows: list[dict[str, Any]] = []
    for record in valid_records:
        z_score, severity = _score_anomaly(db, int(record["item_id"]), int(record["quantity_used"]))
        if severity:
            anomaly_rows.append(
                {
                    "item_id": record["item_id"],
                    "department_id": record["department_id"],
                    "quantity_used": record["quantity_used"],
                    "usage_date": record["usage_date"],
                    "severity": severity,
                    "z_score": z_score,
                }
            )

    return {
        "valid_records": valid_records,
        "invalid_rows": invalid_rows,
        "anomaly_rows": anomaly_rows,
    }
