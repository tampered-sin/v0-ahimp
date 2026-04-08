"""FastAPI routes for purchase-order approval queue and decisions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.db import get_db
from database.po_approval import (
    apply_approval_decision,
    get_approval_detail,
    list_approval_queue,
    process_approval_timeouts,
)
from services.notifications import send_anomaly_alert

router = APIRouter()


class ApprovalDecisionRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    reviewed_by: str = Field(..., min_length=1, max_length=120)
    reviewer_role: str = Field("analyst", min_length=1, max_length=40)
    comment: str | None = Field(default=None, max_length=500)


@router.get("/approval-queue")
def get_approval_queue(
    status: str | None = Query(default=None, max_length=40),
    approval_level: str | None = Query(default=None, max_length=30),
    q: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    process_approval_timeouts(db)
    return list_approval_queue(
        db,
        status=status,
        approval_level=approval_level,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get("/approval-queue/{po_id}")
def get_approval_queue_detail(po_id: int, db: Session = Depends(get_db)):
    process_approval_timeouts(db)
    payload = get_approval_detail(db, po_id=po_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Approval queue item not found")
    return payload


@router.post("/approval-queue/{po_id}/decision")
def decide_approval_queue_item(po_id: int, payload: ApprovalDecisionRequest, db: Session = Depends(get_db)):
    try:
        result = apply_approval_decision(
            db,
            po_id=po_id,
            action=payload.action,
            reviewed_by=payload.reviewed_by,
            reviewer_role=payload.reviewer_role,
            comment=payload.comment,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc

    send_anomaly_alert(
        subject=f"PO-{po_id} approval decision: {result['approval_status']}",
        body=(
            f"PO ID: {po_id}\n"
            f"Action: {payload.action}\n"
            f"Status: {result['approval_status']}\n"
            f"Reviewed by: {payload.reviewed_by} ({payload.reviewer_role})\n"
            f"Comment: {payload.comment or '-'}"
        ),
        severity="RED" if result["approval_status"] == "REJECTED" else "YELLOW",
    )

    return result


@router.post("/approval-queue/auto-timeout")
def trigger_approval_timeout_processing(db: Session = Depends(get_db)):
    updated = process_approval_timeouts(db)

    if updated:
        send_anomaly_alert(
            subject=f"PO auto-approval timeout processed ({len(updated)} items)",
            body="\n".join(
                [
                    f"PO-{row['po_id']}: {row['previous_status']} -> {row['new_status']}"
                    for row in updated
                ]
            ),
            severity="YELLOW",
        )

    return {
        "count": len(updated),
        "items": updated,
    }
