"""Purchase order generation, validation, submission, and tracking workflows."""
from __future__ import annotations

from datetime import date, timedelta
import json
from typing import Any

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from agents.config import AgentTask, BaseAgent
from database.models import (
    Batch,
    DeliveryTracking,
    InventoryStock,
    Item,
    PurchaseOrder,
    PurchaseOrderDetail,
    Supplier,
)
from services.notifications import send_anomaly_alert


DEFAULT_BUDGET_THRESHOLD = 50000.0


def build_purchase_order_payload(
    item_id: int,
    supplier_id: int,
    risk_prob: float = 0.7,
    created_by: str = "system",
    budget_threshold: float = DEFAULT_BUDGET_THRESHOLD,
    discount_pct: float = 0.0,
    submission_method: str = "email",
    supplier_api_url: str | None = None,
) -> dict[str, Any]:
    return {
        "item_id": int(item_id),
        "supplier_id": int(supplier_id),
        "risk_prob": float(risk_prob),
        "created_by": created_by,
        "budget_threshold": float(budget_threshold),
        "discount_pct": float(discount_pct),
        "submission_method": submission_method,
        "supplier_api_url": supplier_api_url,
    }


class PurchaseOrderAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="purchase-order-agent")
        self.registry.register("generate_po_tool", self.generate_po_tool)
        self.registry.register("validate_po_tool", self.validate_po_tool)
        self.registry.register("submit_po_tool", self.submit_po_tool)
        self.registry.register("track_po_tool", self.track_po_tool)

    def _resolve_pricing(self, db: Session, item_id: int, supplier_id: int) -> float:
        avg_price = (
            db.query(func.avg(Batch.purchase_price))
            .filter(Batch.item_id == item_id, Batch.supplier_id == supplier_id)
            .scalar()
        )
        if avg_price is None:
            avg_price = db.query(func.avg(Batch.purchase_price)).filter(Batch.item_id == item_id).scalar()
        if avg_price is None:
            return 1.0
        return max(0.01, float(avg_price))

    def _calculate_quantity(self, db: Session, item: Item, risk_prob: float) -> int:
        reorder = int(item.reorder_point or 10)
        safety_stock = max(reorder, int(round(reorder * 1.5)))

        current_qty = (
            db.query(func.coalesce(func.sum(InventoryStock.current_quantity), 0))
            .filter(InventoryStock.item_id == item.item_id)
            .scalar()
        )
        current_qty = int(current_qty or 0)

        base_qty = max(1, reorder + safety_stock - current_qty)
        multiplier = 1.0 + max(0.0, float(risk_prob) - 0.7) * 2.0
        return max(1, int(round(base_qty * multiplier)))

    def generate_po_tool(
        self,
        db: Session,
        item_id: int,
        supplier_id: int,
        risk_prob: float,
        created_by: str,
        discount_pct: float,
        budget_threshold: float,
    ) -> dict[str, Any]:
        item = db.query(Item).filter(Item.item_id == item_id).first()
        if item is None:
            raise ValueError("Item not found")

        supplier = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
        if supplier is None:
            raise ValueError("Supplier not found")

        quantity = self._calculate_quantity(db, item, risk_prob)
        unit_price = self._resolve_pricing(db, item_id, supplier_id)
        discount = max(0.0, min(30.0, float(discount_pct)))
        subtotal = float(quantity) * float(unit_price)
        total_cost = round(subtotal * (1.0 - discount / 100.0), 2)

        lead_days = int(supplier.avg_lead_time_days or 7)
        expected_delivery = date.today() + timedelta(days=max(1, lead_days))

        validation = self.validate_po_tool(
            db,
            item_id=item_id,
            supplier_id=supplier_id,
            total_cost=total_cost,
            budget_threshold=budget_threshold,
        )

        if not validation["valid"]:
            issues = ",".join(validation.get("issues", [])) or "validation_failed"
            raise ValueError(f"PO validation failed: {issues}")

        po_status = "PENDING_APPROVAL" if validation["approval_required"] else "APPROVED"
        po = PurchaseOrder(
            supplier_id=supplier_id,
            order_date=date.today(),
            expected_delivery=expected_delivery,
            status=po_status,
        )
        db.add(po)
        db.flush()

        detail = PurchaseOrderDetail(
            po_id=int(po.po_id),
            item_id=item_id,
            quantity=quantity,
            unit_price=unit_price,
            discount_pct=discount,
            total_cost=total_cost,
            created_by=created_by,
            approval_required=validation["approval_required"],
            approval_status="PENDING" if validation["approval_required"] else "APPROVED",
            submission_method=None,
            submission_status="PENDING",
            supplier_api_url=None,
            submission_payload=None,
            tracking_reference=f"PO-{po.po_id}",
        )
        db.add(detail)
        db.commit()
        db.refresh(po)
        db.refresh(detail)

        if validation["approval_required"]:
            send_anomaly_alert(
                subject=f"Purchase Order Approval Required: PO-{po.po_id}",
                body=(
                    f"PO {po.po_id} for item {item.item_name} requires approval.\n"
                    f"Total cost: {total_cost}\n"
                    f"Budget threshold: {budget_threshold}"
                ),
                severity="YELLOW",
            )

        return {
            "po_id": int(po.po_id),
            "detail_id": int(detail.detail_id),
            "item_id": item_id,
            "item_name": item.item_name,
            "supplier_id": supplier_id,
            "supplier_name": supplier.supplier_name,
            "quantity": quantity,
            "unit_price": round(unit_price, 4),
            "discount_pct": discount,
            "total_cost": total_cost,
            "order_date": str(po.order_date) if po.order_date else None,
            "expected_delivery": str(po.expected_delivery) if po.expected_delivery else None,
            "status": po.status,
            "approval_required": validation["approval_required"],
            "validation": validation,
        }

    def validate_po_tool(
        self,
        db: Session,
        item_id: int,
        supplier_id: int,
        total_cost: float,
        budget_threshold: float,
    ) -> dict[str, Any]:
        supplier_exists = db.query(Supplier.supplier_id).filter(Supplier.supplier_id == supplier_id).first() is not None
        if not supplier_exists:
            return {
                "valid": False,
                "supplier_available": False,
                "duplicate_recent_order": False,
                "approval_required": False,
                "issues": ["supplier_not_available"],
            }

        seven_days_ago = date.today() - timedelta(days=7)
        duplicate = (
            db.query(PurchaseOrderDetail.detail_id)
            .join(PurchaseOrder, PurchaseOrderDetail.po_id == PurchaseOrder.po_id)
            .filter(
                PurchaseOrderDetail.item_id == item_id,
                PurchaseOrder.supplier_id == supplier_id,
                PurchaseOrder.order_date >= seven_days_ago,
                PurchaseOrder.status.notin_(["CANCELLED"]),
            )
            .first()
            is not None
        )

        approval_required = float(total_cost) > float(budget_threshold)
        issues: list[str] = []
        if duplicate:
            issues.append("duplicate_order_last_7_days")
        if approval_required:
            issues.append("budget_approval_required")

        return {
            "valid": not duplicate,
            "supplier_available": True,
            "duplicate_recent_order": duplicate,
            "approval_required": approval_required,
            "issues": issues,
        }

    def _build_submission_payload(
        self,
        po: PurchaseOrder,
        detail: PurchaseOrderDetail,
        method: str,
    ) -> tuple[str, str]:
        if method == "edi":
            payload = (
                f"UNH+{po.po_id}+ORDERS:D:96A:UN\n"
                f"BGM+220+PO{po.po_id}+9\n"
                f"DTM+137:{po.order_date.strftime('%Y%m%d') if po.order_date else ''}:102\n"
                f"LIN+1++ITEM{detail.item_id}:IN\n"
                f"QTY+21:{detail.quantity}\n"
                f"PRI+AAA:{detail.unit_price}\n"
                f"UNS+S\n"
                f"UNT+7+{po.po_id}"
            )
            return payload, "EDI_SENT"

        if method == "api":
            payload = json.dumps(
                {
                    "po_id": int(po.po_id),
                    "item_id": int(detail.item_id),
                    "quantity": int(detail.quantity),
                    "total_cost": float(detail.total_cost),
                    "expected_delivery": str(po.expected_delivery) if po.expected_delivery else None,
                }
            )
            return payload, "API_QUEUED"

        # email default with CSV-style attachment payload
        payload = (
            "po_id,item_id,quantity,unit_price,total_cost\n"
            f"{po.po_id},{detail.item_id},{detail.quantity},{detail.unit_price},{detail.total_cost}"
        )
        return payload, "EMAIL_QUEUED"

    def submit_po_tool(
        self,
        db: Session,
        po_id: int,
        method: str,
        supplier_api_url: str | None = None,
    ) -> dict[str, Any]:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_id == po_id).first()
        if po is None:
            raise ValueError("Purchase order not found")

        detail = db.query(PurchaseOrderDetail).filter(PurchaseOrderDetail.po_id == po_id).first()
        if detail is None:
            raise ValueError("Purchase order detail not found")

        normalized_method = method.strip().lower()
        if normalized_method not in {"edi", "email", "api"}:
            raise ValueError("Unsupported submission method")

        payload, submission_status = self._build_submission_payload(po, detail, normalized_method)

        if normalized_method == "api" and supplier_api_url:
            try:
                response = httpx.post(supplier_api_url, content=payload, timeout=10.0)
                submission_status = "API_SENT" if response.status_code < 400 else "API_FAILED"
            except Exception:
                submission_status = "API_FAILED"

        detail.submission_method = normalized_method.upper()
        detail.submission_status = submission_status
        detail.supplier_api_url = supplier_api_url
        detail.submission_payload = payload

        if submission_status.endswith("FAILED"):
            po.status = "SUBMISSION_FAILED"
            send_anomaly_alert(
                subject=f"PO submission failed: PO-{po_id}",
                body=f"Submission method: {normalized_method}\nPO: {po_id}",
                severity="RED",
            )
        else:
            po.status = "SUBMITTED"

            tracking_reference = detail.tracking_reference or f"PO-{po_id}"
            detail.tracking_reference = tracking_reference
            delivery = (
                db.query(DeliveryTracking)
                .filter(DeliveryTracking.tracking_reference == tracking_reference)
                .first()
            )
            if delivery is None:
                delivery = DeliveryTracking(
                    po_id=int(po.po_id),
                    tracking_reference=tracking_reference,
                    carrier_name=("supplier_api" if normalized_method == "api" else normalized_method),
                    status="CONFIRMED",
                    expected_delivery=po.expected_delivery,
                    last_event_code="SUBMIT",
                    last_event_message=f"PO submitted via {normalized_method}",
                    delay_reason=None,
                )
                db.add(delivery)
            else:
                delivery.status = "CONFIRMED"
                delivery.expected_delivery = po.expected_delivery
                delivery.last_event_code = "SUBMIT"
                delivery.last_event_message = f"PO submitted via {normalized_method}"
                delivery.delay_reason = None

        db.commit()

        return {
            "po_id": int(po.po_id),
            "method": normalized_method,
            "submission_status": submission_status,
            "po_status": po.status,
        }

    def track_po_tool(self, db: Session, po_id: int) -> dict[str, Any]:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_id == po_id).first()
        if po is None:
            raise ValueError("Purchase order not found")

        detail = db.query(PurchaseOrderDetail).filter(PurchaseOrderDetail.po_id == po_id).first()
        delivery = (
            db.query(DeliveryTracking)
            .filter(DeliveryTracking.po_id == po_id)
            .order_by(DeliveryTracking.delivery_id.desc())
            .first()
        )

        delayed = bool(
            po.expected_delivery
            and po.expected_delivery < date.today()
            and str(po.status or "").upper() not in {"DELIVERED", "CANCELLED"}
        )
        if delayed and po.status != "DELAYED":
            po.status = "DELAYED"
            send_anomaly_alert(
                subject=f"Delayed delivery alert: PO-{po_id}",
                body=f"Expected delivery was {po.expected_delivery}",
                severity="YELLOW",
            )

        if delivery is not None:
            delayed = bool(
                delivery.expected_delivery
                and delivery.expected_delivery < date.today()
                and str(delivery.status or "").upper() not in {"DELIVERED", "CANCELLED"}
            )
            if delayed and delivery.status != "DELAYED":
                delivery.status = "DELAYED"
                if not delivery.delay_reason:
                    delivery.delay_reason = "expected_delivery_breached"

        db.commit()

        return {
            "po_id": int(po.po_id),
            "status": delivery.status if delivery is not None else po.status,
            "expected_delivery": str(po.expected_delivery) if po.expected_delivery else None,
            "delayed": delayed,
            "tracking_reference": (
                (delivery.tracking_reference if delivery is not None else None)
                or (detail.tracking_reference if detail else None)
            ),
        }

    def execute(self, task: AgentTask, context: dict[str, Any] | None = None) -> dict:
        context = context or {}
        db: Session | None = context.get("db")
        if db is None:
            raise ValueError("PurchaseOrderAgent requires context['db']")

        payload = task.payload or {}
        generated = self.generate_po_tool(
            db,
            item_id=int(payload["item_id"]),
            supplier_id=int(payload["supplier_id"]),
            risk_prob=float(payload.get("risk_prob", 0.7)),
            created_by=str(payload.get("created_by", "system")),
            discount_pct=float(payload.get("discount_pct", 0.0)),
            budget_threshold=float(payload.get("budget_threshold", DEFAULT_BUDGET_THRESHOLD)),
        )

        submitted = self.submit_po_tool(
            db,
            po_id=int(generated["po_id"]),
            method=str(payload.get("submission_method", "email")),
            supplier_api_url=payload.get("supplier_api_url"),
        )

        tracking = self.track_po_tool(db, po_id=int(generated["po_id"]))

        return {
            "generated": generated,
            "submitted": submitted,
            "tracking": tracking,
        }
