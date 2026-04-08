"""FastAPI routes for purchase order creation, submission, and tracking."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agents.config import AgentTask
from agents.purchase_order_agent import PurchaseOrderAgent, build_purchase_order_payload
from database.db import get_db
from database.models import PurchaseOrder, PurchaseOrderDetail

router = APIRouter()


class PurchaseOrderCreateRequest(BaseModel):
    item_id: int = Field(..., ge=1)
    supplier_id: int = Field(..., ge=1)
    risk_prob: float = Field(0.7, ge=0.0, le=1.0)
    created_by: str = Field("system", min_length=1, max_length=100)
    budget_threshold: float = Field(50000.0, gt=0)
    discount_pct: float = Field(0.0, ge=0.0, le=30.0)
    submission_method: str = Field("email", pattern="^(edi|email|api)$")
    supplier_api_url: str | None = None


class PurchaseOrderStatusUpdateRequest(BaseModel):
    status: str = Field(..., min_length=2, max_length=50)


class PurchaseOrderSubmitRequest(BaseModel):
    method: str = Field(..., pattern="^(edi|email|api)$")
    supplier_api_url: str | None = None


def _agent_run(payload: PurchaseOrderCreateRequest, db: Session) -> dict:
    agent = PurchaseOrderAgent()
    task = AgentTask(
        name="purchase_order_generation",
        description="Generate, validate, submit and track purchase order",
        payload=build_purchase_order_payload(
            item_id=payload.item_id,
            supplier_id=payload.supplier_id,
            risk_prob=payload.risk_prob,
            created_by=payload.created_by,
            budget_threshold=payload.budget_threshold,
            discount_pct=payload.discount_pct,
            submission_method=payload.submission_method,
            supplier_api_url=payload.supplier_api_url,
        ),
    )
    return agent.run(task=task, context={"db": db})


@router.post("/purchase-orders")
def create_purchase_order(payload: PurchaseOrderCreateRequest, db: Session = Depends(get_db)):
    result = _agent_run(payload, db)
    if not result.get("ok"):
        message = str(result.get("error", "Purchase order creation failed"))
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message)
    return result


@router.get("/purchase-orders")
def list_purchase_orders(status: str | None = None, limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    query = db.query(PurchaseOrder, PurchaseOrderDetail).outerjoin(
        PurchaseOrderDetail, PurchaseOrder.po_id == PurchaseOrderDetail.po_id
    )
    if status:
        query = query.filter(PurchaseOrder.status == status)

    rows = (
        query.order_by(PurchaseOrder.po_id.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 500)))
        .all()
    )

    items: list[dict] = []
    for po, detail in rows:
        items.append(
            {
                "po_id": int(po.po_id),
                "supplier_id": po.supplier_id,
                "order_date": str(po.order_date) if po.order_date else None,
                "expected_delivery": str(po.expected_delivery) if po.expected_delivery else None,
                "status": po.status,
                "item_id": detail.item_id if detail else None,
                "quantity": detail.quantity if detail else None,
                "total_cost": detail.total_cost if detail else None,
                "created_by": detail.created_by if detail else None,
                "submission_method": detail.submission_method if detail else None,
                "submission_status": detail.submission_status if detail else None,
                "tracking_reference": detail.tracking_reference if detail else None,
            }
        )

    return {"count": len(items), "items": items}


@router.get("/purchase-orders/{po_id}")
def get_purchase_order(po_id: int, db: Session = Depends(get_db)):
    row = (
        db.query(PurchaseOrder, PurchaseOrderDetail)
        .outerjoin(PurchaseOrderDetail, PurchaseOrder.po_id == PurchaseOrderDetail.po_id)
        .filter(PurchaseOrder.po_id == po_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    po, detail = row
    return {
        "po_id": int(po.po_id),
        "supplier_id": po.supplier_id,
        "order_date": str(po.order_date) if po.order_date else None,
        "expected_delivery": str(po.expected_delivery) if po.expected_delivery else None,
        "status": po.status,
        "detail": {
            "item_id": detail.item_id if detail else None,
            "quantity": detail.quantity if detail else None,
            "unit_price": detail.unit_price if detail else None,
            "total_cost": detail.total_cost if detail else None,
            "discount_pct": detail.discount_pct if detail else None,
            "created_by": detail.created_by if detail else None,
            "approval_status": detail.approval_status if detail else None,
            "submission_method": detail.submission_method if detail else None,
            "submission_status": detail.submission_status if detail else None,
            "tracking_reference": detail.tracking_reference if detail else None,
        },
    }


@router.patch("/purchase-orders/{po_id}/status")
def update_purchase_order_status(
    po_id: int,
    payload: PurchaseOrderStatusUpdateRequest,
    db: Session = Depends(get_db),
):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.po_id == po_id).first()
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    po.status = payload.status.strip().upper()
    if po.status == "DELIVERED" and po.expected_delivery and po.expected_delivery < date.today():
        po.status = "DELIVERED_LATE"

    db.commit()
    return {
        "po_id": int(po.po_id),
        "status": po.status,
    }


@router.post("/purchase-orders/{po_id}/submit")
def submit_purchase_order(po_id: int, payload: PurchaseOrderSubmitRequest, db: Session = Depends(get_db)):
    agent = PurchaseOrderAgent()
    try:
        out = agent.submit_po_tool(
            db,
            po_id=po_id,
            method=payload.method,
            supplier_api_url=payload.supplier_api_url,
        )
        return out
    except ValueError as exc:
        message = str(exc)
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message) from exc


@router.get("/purchase-orders/{po_id}/tracking")
def get_purchase_order_tracking(po_id: int, db: Session = Depends(get_db)):
    agent = PurchaseOrderAgent()
    try:
        return agent.track_po_tool(db, po_id=po_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
