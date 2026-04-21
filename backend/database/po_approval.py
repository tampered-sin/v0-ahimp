"""Helpers for purchase-order approval rules, queue queries, and audit trail."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from database.models import (
    Item,
    PurchaseOrder,
    PurchaseOrderApproval,
    PurchaseOrderApprovalAudit,
    PurchaseOrderDetail,
    Supplier,
)

AUTO_APPROVE_LIMIT = 5000.0
ESCALATION_LIMIT = 50000.0
HIGH_RELIABILITY_THRESHOLD = 0.85
APPROVAL_TIMEOUT_HOURS = 24

_PENDING_STATUSES = {"PENDING_REVIEW", "PENDING_MANAGER_REVIEW"}


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def evaluate_po_approval_rule(
    *,
    total_cost: float,
    supplier_reliability: float | None,
    is_new_supplier: bool,
    auto_approve_limit: float = AUTO_APPROVE_LIMIT,
    escalation_limit: float = ESCALATION_LIMIT,
    high_reliability_threshold: float = HIGH_RELIABILITY_THRESHOLD,
) -> dict[str, Any]:
    reliability = float(supplier_reliability or 0.0)
    high_reliability = reliability >= float(high_reliability_threshold)

    reasons: list[str] = []
    approval_level = "AUTO"
    approval_status = "AUTO_APPROVED"
    approval_required = False
    escalation_required = False

    if float(total_cost) > float(escalation_limit):
        approval_level = "MANAGER"
        approval_status = "PENDING_MANAGER_REVIEW"
        approval_required = True
        escalation_required = True
        reasons.append("amount_exceeds_manager_threshold")
    elif float(total_cost) >= float(auto_approve_limit) or is_new_supplier or not high_reliability:
        approval_level = "MANUAL"
        approval_status = "PENDING_REVIEW"
        approval_required = True
        if float(total_cost) >= float(auto_approve_limit):
            reasons.append("amount_requires_manual_review")
        if is_new_supplier:
            reasons.append("new_supplier_requires_review")
        if not high_reliability:
            reasons.append("supplier_reliability_below_threshold")
    else:
        reasons.append("low_amount_and_high_reliability_auto_approved")

    return {
        "approval_required": approval_required,
        "approval_level": approval_level,
        "approval_status": approval_status,
        "escalation_required": escalation_required,
        "approval_reason": ",".join(reasons),
        "score_breakdown": {
            "total_cost": float(round(total_cost, 2)),
            "supplier_reliability": reliability,
            "is_new_supplier": bool(is_new_supplier),
            "high_reliability": high_reliability,
            "auto_approve_limit": float(auto_approve_limit),
            "escalation_limit": float(escalation_limit),
        },
        "rule_snapshot": {
            "evaluated_at": _utc_now().isoformat(),
            "auto_approve_limit": float(auto_approve_limit),
            "escalation_limit": float(escalation_limit),
            "high_reliability_threshold": float(high_reliability_threshold),
        },
    }


def append_approval_audit(
    db: Session,
    *,
    po_id: int,
    event_type: str,
    previous_status: str | None,
    new_status: str,
    actor: str,
    comment: str | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> None:
    row = PurchaseOrderApprovalAudit(
        po_id=po_id,
        event_type=event_type,
        previous_status=previous_status,
        new_status=new_status,
        actor=actor,
        comment=comment,
        metadata_json=metadata_json,
    )
    db.add(row)


def upsert_po_approval(
    db: Session,
    *,
    po_id: int,
    decision: dict[str, Any],
    notification_alert_id: int | None = None,
) -> PurchaseOrderApproval:
    row = db.query(PurchaseOrderApproval).filter(PurchaseOrderApproval.po_id == po_id).first()
    if row is None:
        row = PurchaseOrderApproval(po_id=po_id)
        db.add(row)

    row.approval_level = str(decision["approval_level"])
    row.approval_status = str(decision["approval_status"])
    row.escalation_required = bool(decision["escalation_required"])
    row.approval_reason = str(decision.get("approval_reason") or "")
    row.score_breakdown = decision.get("score_breakdown")
    row.rule_snapshot = decision.get("rule_snapshot")
    row.requested_at = _utc_now()
    row.notification_alert_id = notification_alert_id

    if row.approval_status in _PENDING_STATUSES:
        row.due_at = _utc_now() + timedelta(hours=APPROVAL_TIMEOUT_HOURS)
        row.decided_at = None
        row.decided_by = None
        row.decision_comment = None
    else:
        row.due_at = None
        row.decided_at = _utc_now()
        row.decided_by = "rules-engine"
        row.decision_comment = row.approval_reason

    return row


def _serialize_approval(
    approval: PurchaseOrderApproval,
    po: PurchaseOrder,
    detail: PurchaseOrderDetail | None,
    supplier_name: str | None,
    item_name: str | None,
    last_event: PurchaseOrderApprovalAudit | None,
) -> dict[str, Any]:
    return {
        "po_id": int(po.po_id),
        "supplier_id": int(po.supplier_id) if po.supplier_id is not None else None,
        "supplier_name": supplier_name,
        "item_id": int(detail.item_id) if detail and detail.item_id is not None else None,
        "item_name": item_name,
        "quantity": int(detail.quantity) if detail and detail.quantity is not None else None,
        "total_cost": float(detail.total_cost) if detail and detail.total_cost is not None else None,
        "po_status": po.status,
        "approval_level": approval.approval_level,
        "approval_status": approval.approval_status,
        "escalation_required": bool(approval.escalation_required),
        "approval_reason": approval.approval_reason,
        "score_breakdown": approval.score_breakdown,
        "rule_snapshot": approval.rule_snapshot,
        "requested_at": approval.requested_at.isoformat() if approval.requested_at else None,
        "due_at": approval.due_at.isoformat() if approval.due_at else None,
        "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
        "decided_by": approval.decided_by,
        "decision_comment": approval.decision_comment,
        "last_audit_event": (
            {
                "event_type": last_event.event_type,
                "new_status": last_event.new_status,
                "actor": last_event.actor,
                "comment": last_event.comment,
                "created_at": last_event.created_at.isoformat() if last_event.created_at else None,
            }
            if last_event
            else None
        ),
    }


def process_approval_timeouts(db: Session, now: datetime | None = None) -> list[dict[str, Any]]:
    current = now or _utc_now()
    rows = (
        db.query(PurchaseOrderApproval, PurchaseOrder, PurchaseOrderDetail)
        .join(PurchaseOrder, PurchaseOrderApproval.po_id == PurchaseOrder.po_id)
        .join(PurchaseOrderDetail, PurchaseOrder.po_id == PurchaseOrderDetail.po_id)
        .filter(PurchaseOrderApproval.approval_status.in_(list(_PENDING_STATUSES)))
        .filter(PurchaseOrderApproval.due_at.isnot(None))
        .filter(PurchaseOrderApproval.due_at <= current)
        .all()
    )

    updated: list[dict[str, Any]] = []
    for approval, po, detail in rows:
        previous = approval.approval_status
        approval.approval_status = "AUTO_APPROVED_TIMEOUT"
        approval.decided_at = current
        approval.decided_by = "system-timeout"
        approval.decision_comment = "Auto-approved after 24h timeout"

        detail.approval_required = False
        detail.approval_status = "AUTO_APPROVED_TIMEOUT"
        po.status = "APPROVED"

        append_approval_audit(
            db,
            po_id=int(po.po_id),
            event_type="TIMEOUT_AUTO_APPROVED",
            previous_status=previous,
            new_status=approval.approval_status,
            actor="system-timeout",
            comment=approval.decision_comment,
            metadata_json={"due_at": approval.due_at.isoformat() if approval.due_at else None},
        )

        updated.append(
            {
                "po_id": int(po.po_id),
                "previous_status": previous,
                "new_status": approval.approval_status,
            }
        )

    if updated:
        db.commit()

    return updated


def list_approval_queue(
    db: Session,
    *,
    status: str | None = None,
    approval_level: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    query = (
        db.query(
            PurchaseOrderApproval,
            PurchaseOrder,
            PurchaseOrderDetail,
            Supplier.supplier_name,
            Item.item_name,
        )
        .join(PurchaseOrder, PurchaseOrderApproval.po_id == PurchaseOrder.po_id)
        .outerjoin(PurchaseOrderDetail, PurchaseOrder.po_id == PurchaseOrderDetail.po_id)
        .outerjoin(Supplier, PurchaseOrder.supplier_id == Supplier.supplier_id)
        .outerjoin(Item, PurchaseOrderDetail.item_id == Item.item_id)
    )

    if status:
        query = query.filter(PurchaseOrderApproval.approval_status == status)
    if approval_level:
        query = query.filter(PurchaseOrderApproval.approval_level == approval_level)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                cast(PurchaseOrder.po_id, String).ilike(pattern),
                Supplier.supplier_name.ilike(pattern),
                Item.item_name.ilike(pattern),
                PurchaseOrderApproval.approval_reason.ilike(pattern),
            )
        )

    total = query.count()
    rows = (
        query.order_by(PurchaseOrderApproval.requested_at.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 500)))
        .all()
    )

    po_ids = [int(po.po_id) for _, po, _, _, _ in rows]
    latest_by_po: dict[int, PurchaseOrderApprovalAudit] = {}
    if po_ids:
        audit_rows = (
            db.query(PurchaseOrderApprovalAudit)
            .filter(PurchaseOrderApprovalAudit.po_id.in_(po_ids))
            .order_by(PurchaseOrderApprovalAudit.po_id.asc(), PurchaseOrderApprovalAudit.audit_id.desc())
            .all()
        )
        for row in audit_rows:
            po_id = int(row.po_id)
            if po_id not in latest_by_po:
                latest_by_po[po_id] = row

    items = [
        _serialize_approval(
            approval=approval,
            po=po,
            detail=detail,
            supplier_name=supplier_name,
            item_name=item_name,
            last_event=latest_by_po.get(int(po.po_id)),
        )
        for approval, po, detail, supplier_name, item_name in rows
    ]

    return {
        "count": total,
        "items": items,
    }


def get_approval_detail(db: Session, po_id: int) -> dict[str, Any] | None:
    row = (
        db.query(
            PurchaseOrderApproval,
            PurchaseOrder,
            PurchaseOrderDetail,
            Supplier.supplier_name,
            Item.item_name,
        )
        .join(PurchaseOrder, PurchaseOrderApproval.po_id == PurchaseOrder.po_id)
        .outerjoin(PurchaseOrderDetail, PurchaseOrder.po_id == PurchaseOrderDetail.po_id)
        .outerjoin(Supplier, PurchaseOrder.supplier_id == Supplier.supplier_id)
        .outerjoin(Item, PurchaseOrderDetail.item_id == Item.item_id)
        .filter(PurchaseOrder.po_id == po_id)
        .first()
    )
    if row is None:
        return None

    approval, po, detail, supplier_name, item_name = row
    audits = (
        db.query(PurchaseOrderApprovalAudit)
        .filter(PurchaseOrderApprovalAudit.po_id == po_id)
        .order_by(PurchaseOrderApprovalAudit.audit_id.desc())
        .all()
    )

    payload = _serialize_approval(
        approval=approval,
        po=po,
        detail=detail,
        supplier_name=supplier_name,
        item_name=item_name,
        last_event=audits[0] if audits else None,
    )
    payload["audit_trail"] = [
        {
            "audit_id": int(audit.audit_id),
            "event_type": audit.event_type,
            "previous_status": audit.previous_status,
            "new_status": audit.new_status,
            "actor": audit.actor,
            "comment": audit.comment,
            "metadata": audit.metadata_json,
            "created_at": audit.created_at.isoformat() if audit.created_at else None,
        }
        for audit in audits
    ]
    return payload


def apply_approval_decision(
    db: Session,
    *,
    po_id: int,
    action: str,
    reviewed_by: str,
    reviewer_role: str,
    comment: str | None = None,
) -> dict[str, Any]:
    row = (
        db.query(PurchaseOrderApproval, PurchaseOrder, PurchaseOrderDetail)
        .join(PurchaseOrder, PurchaseOrderApproval.po_id == PurchaseOrder.po_id)
        .join(PurchaseOrderDetail, PurchaseOrder.po_id == PurchaseOrderDetail.po_id)
        .filter(PurchaseOrder.po_id == po_id)
        .first()
    )
    if row is None:
        raise ValueError("Approval record not found")

    approval, po, detail = row
    if approval.approval_status not in _PENDING_STATUSES:
        raise ValueError("Approval decision is only allowed for pending records")

    role = reviewer_role.strip().lower()
    if approval.approval_level == "MANAGER" and role not in {"manager", "admin"}:
        raise PermissionError("Manager approval requires reviewer_role=manager|admin")

    normalized_action = action.strip().lower()
    if normalized_action not in {"approve", "reject"}:
        raise ValueError("Unsupported action")

    previous = approval.approval_status
    now = _utc_now()

    if normalized_action == "approve":
        approval.approval_status = "APPROVED"
        po.status = "APPROVED"
        detail.approval_required = False
        detail.approval_status = "APPROVED"
        event = "APPROVED"
    else:
        approval.approval_status = "REJECTED"
        po.status = "REJECTED"
        detail.approval_required = True
        detail.approval_status = "REJECTED"
        detail.submission_status = "CANCELLED"
        event = "REJECTED"

    approval.decided_at = now
    approval.decided_by = reviewed_by
    approval.decision_comment = comment

    append_approval_audit(
        db,
        po_id=po_id,
        event_type=event,
        previous_status=previous,
        new_status=approval.approval_status,
        actor=reviewed_by,
        comment=comment,
        metadata_json={"reviewer_role": role},
    )

    db.commit()

    return {
        "po_id": po_id,
        "action": normalized_action,
        "approval_status": approval.approval_status,
        "po_status": po.status,
        "reviewed_by": reviewed_by,
        "reviewer_role": role,
        "comment": comment,
        "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
    }
