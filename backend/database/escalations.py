"""Escalation logging helpers for supply chain human handoffs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from database.models import EscalationLog


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _serialize(row: EscalationLog) -> dict[str, Any]:
    context = row.context or {}
    status = str(context.get("status", "OPEN")).upper()
    return {
        "escalation_id": int(row.escalation_id),
        "triggered_by": row.triggered_by,
        "reason": row.reason,
        "medicine": row.medicine,
        "quantity_needed": int(row.quantity_needed),
        "stockout_risk": float(row.stockout_risk),
        "days_until_stockout": int(row.days_until_stockout),
        "suppliers_evaluated": row.suppliers_evaluated or [],
        "recommended_action": row.recommended_action,
        "priority": row.priority,
        "status": status,
        "context": context,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def create_escalation_log(
    db: Session,
    *,
    triggered_by: str,
    reason: str,
    medicine: str,
    quantity_needed: int,
    stockout_risk: float,
    days_until_stockout: int,
    suppliers_evaluated: list[dict[str, Any]] | None = None,
    recommended_action: str,
    priority: str = "HIGH",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged_context = {
        "status": "OPEN",
        **(context or {}),
    }
    row = EscalationLog(
        triggered_by=triggered_by,
        reason=reason,
        medicine=medicine,
        quantity_needed=max(1, int(quantity_needed)),
        stockout_risk=float(stockout_risk),
        days_until_stockout=max(1, int(days_until_stockout)),
        suppliers_evaluated=suppliers_evaluated or [],
        recommended_action=recommended_action,
        priority=str(priority).upper(),
        context=merged_context,
        created_at=_utc_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize(row)


def list_escalations(
    db: Session,
    *,
    status: str = "OPEN",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    normalized = str(status or "OPEN").upper()
    query = db.query(EscalationLog)
    rows = query.order_by(EscalationLog.days_until_stockout.asc(), EscalationLog.created_at.desc()).all()

    filtered = []
    for row in rows:
        row_context = row.context or {}
        row_status = str(row_context.get("status", "OPEN")).upper()
        if normalized == "ALL" or row_status == normalized:
            filtered.append(row)

    sliced = filtered[offset: offset + max(1, int(limit))]
    return {
        "count": len(filtered),
        "records": [_serialize(row) for row in sliced],
    }


def resolve_escalation(
    db: Session,
    *,
    escalation_id: int,
    action: str,
    resolution_note: str,
    resolved_by: str,
) -> dict[str, Any]:
    if not resolution_note or not resolution_note.strip():
        raise ValueError("resolution_note is required")

    action_up = str(action or "").upper()
    if action_up not in {"RESOLVED", "DISMISSED"}:
        raise ValueError("action must be RESOLVED or DISMISSED")

    row = db.query(EscalationLog).filter(EscalationLog.escalation_id == int(escalation_id)).first()
    if row is None:
        raise ValueError("Escalation not found")

    context = dict(row.context or {})
    context.update(
        {
            "status": action_up,
            "resolution_note": resolution_note.strip(),
            "resolved_by": str(resolved_by or "system"),
            "resolved_at": _utc_now().isoformat(),
        }
    )
    row.context = context
    db.commit()
    db.refresh(row)
    return _serialize(row)
