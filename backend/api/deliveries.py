"""FastAPI routes for delivery tracking and delay alerts."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from agents.config import AgentTask
from agents.delivery_tracker import DeliveryTrackerAgent, build_delivery_tracker_payload
from database.db import get_db

router = APIRouter()


class DeliveryCreateRequest(BaseModel):
    po_id: int = Field(..., ge=1)
    tracking_reference: str | None = Field(default=None, min_length=2, max_length=120)
    carrier_name: str | None = Field(default=None, min_length=2, max_length=80)
    alert_recipients: list[str] = Field(default_factory=list)


class DeliveryStatusUpdateRequest(BaseModel):
    new_status: str = Field(..., min_length=2, max_length=40)
    tracking_reference: str | None = Field(default=None, min_length=2, max_length=120)
    po_id: int | None = Field(default=None, ge=1)
    reason_code: str | None = Field(default=None, max_length=50)
    event_message: str | None = Field(default=None, max_length=255)
    event_time: datetime | None = None
    source: str = Field("manual", pattern="^(manual|supplier_api|barcode)$")
    carrier_name: str | None = Field(default=None, min_length=2, max_length=80)
    raw_payload: dict[str, Any] | None = None


class DeliverySyncEvent(BaseModel):
    external_status_code: str = Field(..., min_length=2, max_length=50)
    delivery_id: int | None = Field(default=None, ge=1)
    tracking_reference: str | None = Field(default=None, min_length=2, max_length=120)
    barcode: str | None = Field(default=None, min_length=2, max_length=120)
    po_id: int | None = Field(default=None, ge=1)
    reason_code: str | None = Field(default=None, max_length=50)
    event_time: datetime | None = None
    source: str = Field("supplier_api", pattern="^(supplier_api|manual|barcode)$")
    event_message: str | None = Field(default=None, max_length=255)
    carrier_name: str | None = Field(default=None, min_length=2, max_length=80)
    raw_payload: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _require_identifier(self) -> "DeliverySyncEvent":
        if not (self.delivery_id or self.tracking_reference or self.barcode or self.po_id):
            raise ValueError("One of delivery_id, tracking_reference, barcode, or po_id is required")
        return self


class DeliverySyncRequest(BaseModel):
    events: list[DeliverySyncEvent] = Field(default_factory=list, min_length=1)


def _run_delivery_task(db: Session, operation: str, **payload: Any) -> dict[str, Any]:
    agent = DeliveryTrackerAgent()
    task = AgentTask(
        name="delivery_tracking",
        description="Manage delivery state transitions and alerts",
        payload=build_delivery_tracker_payload(operation=operation, **payload),
    )
    return agent.run(task=task, context={"db": db})


@router.post("/deliveries/status")
def create_delivery_tracking(payload: DeliveryCreateRequest, db: Session = Depends(get_db)):
    result = _run_delivery_task(
        db,
        operation="create",
        po_id=payload.po_id,
        tracking_reference=payload.tracking_reference,
        carrier_name=payload.carrier_name,
        alert_recipients=payload.alert_recipients,
    )
    if not result.get("ok"):
        message = str(result.get("error", "Failed to create delivery record"))
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message)
    return result["result"]


@router.get("/deliveries/status")
def list_delivery_status(
    status: str | None = None,
    po_id: int | None = None,
    delayed_only: bool = False,
    due_within_days: int | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    result = _run_delivery_task(
        db,
        operation="list",
        status=status,
        po_id=po_id,
        delayed_only=delayed_only,
        due_within_days=due_within_days,
        limit=limit,
        offset=offset,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to list deliveries"))
    return result["result"]


@router.patch("/deliveries/status/{delivery_id}")
def update_delivery_status(
    delivery_id: int,
    payload: DeliveryStatusUpdateRequest,
    db: Session = Depends(get_db),
):
    result = _run_delivery_task(
        db,
        operation="update",
        delivery_id=delivery_id,
        new_status=payload.new_status,
        tracking_reference=payload.tracking_reference,
        po_id=payload.po_id,
        reason_code=payload.reason_code,
        event_message=payload.event_message,
        event_time=payload.event_time.isoformat() if payload.event_time else None,
        source=payload.source,
        carrier_name=payload.carrier_name,
        raw_payload=payload.raw_payload,
    )
    if not result.get("ok"):
        message = str(result.get("error", "Failed to update delivery status"))
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message)

    out = result["result"]
    if not out.get("applied"):
        reason = str(out.get("reason", "status_update_rejected"))
        status_code = 409 if reason == "invalid_transition" else 400
        raise HTTPException(status_code=status_code, detail=out)
    return out


@router.post("/deliveries/sync")
def sync_delivery_events(payload: DeliverySyncRequest, db: Session = Depends(get_db)):
    result = _run_delivery_task(
        db,
        operation="sync",
        events=[entry.model_dump() for entry in payload.events],
    )
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to sync delivery events"))
    return result["result"]
