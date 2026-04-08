"""Delivery tracking agent for shipment state transitions and delay alerts."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from typing import Any

from sqlalchemy.orm import Session

from agents.config import AgentTask, BaseAgent
from database.models import DeliveryEvent, DeliveryTracking, PurchaseOrder, PurchaseOrderDetail
from services.notifications import send_anomaly_alert


DELIVERY_STATES = {
    "PENDING",
    "CONFIRMED",
    "IN_TRANSIT",
    "DELIVERED",
    "DELAYED",
    "CANCELLED",
}
TERMINAL_STATES = {"DELIVERED", "CANCELLED"}

STATE_TRANSITIONS: dict[str, set[str]] = {
    "PENDING": {"CONFIRMED", "CANCELLED"},
    "CONFIRMED": {"IN_TRANSIT", "DELAYED", "CANCELLED"},
    "IN_TRANSIT": {"DELIVERED", "DELAYED", "CANCELLED"},
    "DELAYED": {"IN_TRANSIT", "DELIVERED", "CANCELLED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
}


EXTERNAL_TO_INTERNAL_STATUS = {
    # Internal passthrough
    "PENDING": "PENDING",
    "CONFIRMED": "CONFIRMED",
    "IN_TRANSIT": "IN_TRANSIT",
    "DELIVERED": "DELIVERED",
    "DELAYED": "DELAYED",
    "CANCELLED": "CANCELLED",
    # Common API/event aliases
    "ON_TENDER": "CONFIRMED",
    "ON_SHIPMENT": "CONFIRMED",
    "DEPARTED_FROM_FC": "CONFIRMED",
    "PU": "CONFIRMED",
    "101": "CONFIRMED",
    "IN_PROGRESS": "IN_TRANSIT",
    "OUT_FOR_DELIVERY": "IN_TRANSIT",
    "OD": "IN_TRANSIT",
    "TR": "IN_TRANSIT",
    "IT": "IN_TRANSIT",
    "201": "IN_TRANSIT",
    "302": "IN_TRANSIT",
    "DELIVERED": "DELIVERED",
    "DL": "DELIVERED",
    "301": "DELIVERED",
    "D1": "DELIVERED",
    "ON_DELIVERY": "DELIVERED",
    "DELAY": "DELAYED",
    "ON_EXCEPTION": "DELAYED",
    "DD": "DELAYED",
    "DE": "DELAYED",
    "SE": "DELAYED",
    "CD": "DELAYED",
    "404": "DELAYED",
    "LOST": "DELAYED",
    "UNDELIVERABLE": "DELAYED",
    "CANCEL": "CANCELLED",
    "CA": "CANCELLED",
    "SHIPMENT_CANCELLED": "CANCELLED",
}


def build_delivery_tracker_payload(
    operation: str,
    **kwargs: Any,
) -> dict[str, Any]:
    return {
        "operation": operation,
        **kwargs,
    }


class DeliveryTrackerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="delivery-tracker-agent")
        self.registry.register("create_delivery_tool", self.create_delivery_tool)
        self.registry.register("apply_status_event_tool", self.apply_status_event_tool)
        self.registry.register("evaluate_alerts_tool", self.evaluate_alerts_tool)
        self.registry.register("list_deliveries_tool", self.list_deliveries_tool)
        self.registry.register("sync_events_tool", self.sync_events_tool)

    def _to_utc_datetime(self, event_at: str | datetime | None) -> datetime:
        if isinstance(event_at, datetime):
            dt = event_at
        elif isinstance(event_at, str) and event_at.strip():
            normalized = event_at.strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
        else:
            dt = datetime.now(tz=timezone.utc)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _normalize_status(self, external_status_code: str) -> str:
        normalized = str(external_status_code or "").strip().upper()
        if normalized in EXTERNAL_TO_INTERNAL_STATUS:
            return EXTERNAL_TO_INTERNAL_STATUS[normalized]
        raise ValueError(f"Unsupported external status code: {external_status_code}")

    def _is_transition_allowed(self, current_status: str, next_status: str) -> bool:
        current = str(current_status or "PENDING").upper()
        nxt = str(next_status).upper()
        if current == nxt:
            return True
        if current in TERMINAL_STATES:
            return False
        return nxt in STATE_TRANSITIONS.get(current, set())

    def _serialize_raw_payload(self, raw_payload: dict[str, Any] | str | None) -> str | None:
        if raw_payload is None:
            return None
        if isinstance(raw_payload, str):
            return raw_payload[:3900]
        return json.dumps(raw_payload, separators=(",", ":"), default=str)[:3900]

    def _build_idempotency_key(
        self,
        tracking_reference: str,
        external_status_code: str,
        reason_code: str | None,
        event_at: datetime,
        source: str,
    ) -> str:
        return (
            f"{tracking_reference}|{external_status_code.strip().upper()}|"
            f"{(reason_code or '').strip().upper()}|{event_at.isoformat()}|{source.strip().lower()}"
        )

    def _parse_recipients(self, raw: str | None) -> list[str]:
        if not raw:
            return []
        return [entry.strip() for entry in raw.split(",") if entry.strip()]

    def _compute_alert_level(self, delivery: DeliveryTracking, today: date) -> str:
        status = str(delivery.status or "PENDING").upper()
        if status in TERMINAL_STATES:
            return "NONE"
        if delivery.expected_delivery is None:
            return "NONE"

        overdue_days = (today - delivery.expected_delivery).days
        if overdue_days >= 3:
            return "ESCALATION"
        if overdue_days >= 1:
            return "RED"
        if (delivery.expected_delivery - today).days <= 2:
            return "YELLOW"
        if status == "DELAYED":
            return "RED"
        return "NONE"

    def create_delivery_tool(
        self,
        db: Session,
        po_id: int,
        tracking_reference: str | None = None,
        carrier_name: str | None = None,
        alert_recipients: list[str] | None = None,
    ) -> dict[str, Any]:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_id == int(po_id)).first()
        if po is None:
            raise ValueError("Purchase order not found")

        detail = db.query(PurchaseOrderDetail).filter(PurchaseOrderDetail.po_id == int(po_id)).first()
        resolved_tracking = (tracking_reference or (detail.tracking_reference if detail else None) or f"PO-{po_id}").strip()

        existing = (
            db.query(DeliveryTracking)
            .filter(DeliveryTracking.tracking_reference == resolved_tracking)
            .first()
        )
        if existing is not None:
            return {
                "created": False,
                "delivery_id": int(existing.delivery_id),
                "po_id": int(existing.po_id),
                "tracking_reference": existing.tracking_reference,
                "status": existing.status,
            }

        recipients_csv = ",".join(alert_recipients or []) if alert_recipients else None
        delivery = DeliveryTracking(
            po_id=int(po.po_id),
            tracking_reference=resolved_tracking,
            carrier_name=carrier_name,
            status="PENDING",
            expected_delivery=po.expected_delivery,
            last_event_code="CREATE",
            last_event_message="Delivery tracking initialized",
            last_event_at=datetime.now(tz=timezone.utc),
            delay_reason=None,
            alert_recipients=recipients_csv,
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)

        if detail and not detail.tracking_reference:
            detail.tracking_reference = resolved_tracking
            db.commit()

        return {
            "created": True,
            "delivery_id": int(delivery.delivery_id),
            "po_id": int(delivery.po_id),
            "tracking_reference": delivery.tracking_reference,
            "status": delivery.status,
            "expected_delivery": str(delivery.expected_delivery) if delivery.expected_delivery else None,
        }

    def evaluate_alerts_tool(
        self,
        db: Session,
        delivery_id: int,
        send_alerts: bool = False,
        today: date | None = None,
    ) -> dict[str, Any]:
        delivery = db.query(DeliveryTracking).filter(DeliveryTracking.delivery_id == int(delivery_id)).first()
        if delivery is None:
            raise ValueError("Delivery record not found")

        check_date = today or date.today()
        alert_level = self._compute_alert_level(delivery, check_date)
        should_send = bool(
            send_alerts
            and alert_level != "NONE"
            and alert_level != str(delivery.last_alert_level_sent or "").upper()
        )

        alert_result = None
        if should_send:
            severity = "YELLOW" if alert_level == "YELLOW" else "RED"
            recipients = self._parse_recipients(delivery.alert_recipients)
            days_delta = None
            if delivery.expected_delivery is not None:
                days_delta = (delivery.expected_delivery - check_date).days

            alert_result = send_anomaly_alert(
                subject=f"Delivery {alert_level}: {delivery.tracking_reference}",
                body=(
                    f"Delivery ID: {delivery.delivery_id}\n"
                    f"PO ID: {delivery.po_id}\n"
                    f"Current status: {delivery.status}\n"
                    f"Expected delivery: {delivery.expected_delivery}\n"
                    f"Days to due (negative means overdue): {days_delta}"
                ),
                recipients=recipients or None,
                severity=severity,
            )
            delivery.last_alert_level_sent = alert_level
            db.commit()

        overdue_days = (
            max(0, (check_date - delivery.expected_delivery).days)
            if delivery.expected_delivery is not None and str(delivery.status).upper() not in TERMINAL_STATES
            else 0
        )
        return {
            "delivery_id": int(delivery.delivery_id),
            "tracking_reference": delivery.tracking_reference,
            "alert_level": alert_level,
            "alert_sent": should_send,
            "alert_result": alert_result,
            "overdue_days": overdue_days,
        }

    def apply_status_event_tool(
        self,
        db: Session,
        external_status_code: str,
        delivery_id: int | None = None,
        tracking_reference: str | None = None,
        po_id: int | None = None,
        reason_code: str | None = None,
        event_time: str | datetime | None = None,
        source: str = "manual",
        event_message: str | None = None,
        raw_payload: dict[str, Any] | str | None = None,
        carrier_name: str | None = None,
    ) -> dict[str, Any]:
        delivery = None
        if delivery_id is not None:
            delivery = db.query(DeliveryTracking).filter(DeliveryTracking.delivery_id == int(delivery_id)).first()
        elif tracking_reference:
            delivery = (
                db.query(DeliveryTracking)
                .filter(DeliveryTracking.tracking_reference == tracking_reference.strip())
                .first()
            )

        if delivery is None and po_id is not None:
            created = self.create_delivery_tool(
                db,
                po_id=int(po_id),
                tracking_reference=tracking_reference,
                carrier_name=carrier_name,
            )
            delivery = (
                db.query(DeliveryTracking)
                .filter(DeliveryTracking.delivery_id == int(created["delivery_id"]))
                .first()
            )

        if delivery is None:
            raise ValueError("Delivery record not found")

        normalized_status = self._normalize_status(external_status_code)
        current_status = str(delivery.status or "PENDING").upper()
        if not self._is_transition_allowed(current_status, normalized_status):
            return {
                "applied": False,
                "reason": "invalid_transition",
                "current_status": current_status,
                "next_status": normalized_status,
                "delivery_id": int(delivery.delivery_id),
                "tracking_reference": delivery.tracking_reference,
            }

        parsed_event_time = self._to_utc_datetime(event_time)
        idempotency_key = self._build_idempotency_key(
            delivery.tracking_reference,
            external_status_code,
            reason_code,
            parsed_event_time,
            source,
        )

        duplicate = (
            db.query(DeliveryEvent.event_id)
            .filter(DeliveryEvent.idempotency_key == idempotency_key)
            .first()
        )
        if duplicate is not None:
            return {
                "applied": False,
                "reason": "duplicate_event",
                "delivery_id": int(delivery.delivery_id),
                "tracking_reference": delivery.tracking_reference,
                "idempotency_key": idempotency_key,
            }

        event = DeliveryEvent(
            delivery_id=int(delivery.delivery_id),
            source=source.strip().lower(),
            external_status_code=external_status_code.strip().upper(),
            reason_code=(reason_code.strip().upper() if reason_code else None),
            normalized_status=normalized_status,
            event_message=event_message,
            event_at=parsed_event_time,
            raw_payload=self._serialize_raw_payload(raw_payload),
            idempotency_key=idempotency_key,
        )
        db.add(event)

        delivery.status = normalized_status
        delivery.last_event_code = event.external_status_code
        delivery.last_event_message = event_message
        delivery.last_event_at = parsed_event_time
        if carrier_name:
            delivery.carrier_name = carrier_name

        if normalized_status == "DELIVERED":
            delivery.actual_delivery = parsed_event_time.date()
            delivery.delay_reason = None
        elif normalized_status == "DELAYED":
            delivery.delay_reason = reason_code or event_message or "shipment_exception_or_overdue"
        else:
            delivery.delay_reason = None

        db.commit()

        alert = self.evaluate_alerts_tool(
            db,
            delivery_id=int(delivery.delivery_id),
            send_alerts=True,
        )

        return {
            "applied": True,
            "delivery_id": int(delivery.delivery_id),
            "tracking_reference": delivery.tracking_reference,
            "status": delivery.status,
            "expected_delivery": str(delivery.expected_delivery) if delivery.expected_delivery else None,
            "actual_delivery": str(delivery.actual_delivery) if delivery.actual_delivery else None,
            "alert_level": alert["alert_level"],
            "alert_sent": alert["alert_sent"],
            "idempotency_key": idempotency_key,
        }

    def list_deliveries_tool(
        self,
        db: Session,
        status: str | None = None,
        po_id: int | None = None,
        delayed_only: bool = False,
        due_within_days: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        today = date.today()

        query = db.query(DeliveryTracking)
        if status:
            query = query.filter(DeliveryTracking.status == status.strip().upper())
        if po_id is not None:
            query = query.filter(DeliveryTracking.po_id == int(po_id))

        rows = (
            query.order_by(DeliveryTracking.updated_at.desc())
            .offset(max(0, int(offset)))
            .limit(max(1, min(int(limit), 500)))
            .all()
        )

        items: list[dict[str, Any]] = []
        for delivery in rows:
            if delayed_only:
                is_overdue = bool(
                    delivery.expected_delivery
                    and delivery.expected_delivery < today
                    and str(delivery.status or "").upper() not in TERMINAL_STATES
                )
                if str(delivery.status or "").upper() != "DELAYED" and not is_overdue:
                    continue

            if due_within_days is not None and delivery.expected_delivery is not None:
                max_due_date = today + timedelta(days=max(0, int(due_within_days)))
                if delivery.expected_delivery > max_due_date:
                    continue

            active_alert_level = self._compute_alert_level(delivery, today)
            overdue_days = (
                max(0, (today - delivery.expected_delivery).days)
                if delivery.expected_delivery is not None and str(delivery.status or "").upper() not in TERMINAL_STATES
                else 0
            )
            days_to_due = (
                (delivery.expected_delivery - today).days if delivery.expected_delivery is not None else None
            )

            items.append(
                {
                    "delivery_id": int(delivery.delivery_id),
                    "po_id": int(delivery.po_id),
                    "tracking_reference": delivery.tracking_reference,
                    "carrier_name": delivery.carrier_name,
                    "status": delivery.status,
                    "expected_delivery": str(delivery.expected_delivery) if delivery.expected_delivery else None,
                    "actual_delivery": str(delivery.actual_delivery) if delivery.actual_delivery else None,
                    "last_event_code": delivery.last_event_code,
                    "last_event_message": delivery.last_event_message,
                    "last_event_at": delivery.last_event_at.isoformat() if delivery.last_event_at else None,
                    "delay_reason": delivery.delay_reason,
                    "overdue_days": overdue_days,
                    "days_to_due": days_to_due,
                    "active_alert_level": active_alert_level,
                }
            )

        return {"count": len(items), "items": items}

    def sync_events_tool(self, db: Session, events: list[dict[str, Any]]) -> dict[str, Any]:
        applied: list[dict[str, Any]] = []
        duplicates: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        for idx, event in enumerate(events):
            try:
                out = self.apply_status_event_tool(
                    db,
                    external_status_code=str(event.get("external_status_code", "")),
                    delivery_id=event.get("delivery_id"),
                    tracking_reference=event.get("tracking_reference") or event.get("barcode"),
                    po_id=event.get("po_id"),
                    reason_code=event.get("reason_code"),
                    event_time=event.get("event_time"),
                    source=str(event.get("source", "supplier_api")),
                    event_message=event.get("event_message"),
                    raw_payload=event.get("raw_payload"),
                    carrier_name=event.get("carrier_name"),
                )
                if out.get("applied"):
                    applied.append(out)
                elif out.get("reason") == "duplicate_event":
                    duplicates.append(out)
                else:
                    rejected.append(out)
            except Exception as exc:
                rejected.append(
                    {
                        "index": idx,
                        "applied": False,
                        "reason": "exception",
                        "error": str(exc),
                    }
                )

        return {
            "received": len(events),
            "applied": len(applied),
            "duplicates": len(duplicates),
            "rejected": len(rejected),
            "applied_events": applied,
            "duplicate_events": duplicates,
            "rejected_events": rejected,
        }

    def execute(self, task: AgentTask, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        db: Session | None = context.get("db")
        if db is None:
            raise ValueError("DeliveryTrackerAgent requires context['db']")

        payload = task.payload or {}
        operation = str(payload.get("operation", "list")).strip().lower()

        if operation == "create":
            return self.create_delivery_tool(
                db,
                po_id=int(payload["po_id"]),
                tracking_reference=payload.get("tracking_reference"),
                carrier_name=payload.get("carrier_name"),
                alert_recipients=payload.get("alert_recipients") or [],
            )

        if operation == "list":
            return self.list_deliveries_tool(
                db,
                status=payload.get("status"),
                po_id=payload.get("po_id"),
                delayed_only=bool(payload.get("delayed_only", False)),
                due_within_days=payload.get("due_within_days"),
                limit=int(payload.get("limit", 100)),
                offset=int(payload.get("offset", 0)),
            )

        if operation == "update":
            return self.apply_status_event_tool(
                db,
                external_status_code=str(payload["new_status"]),
                delivery_id=payload.get("delivery_id"),
                tracking_reference=payload.get("tracking_reference"),
                po_id=payload.get("po_id"),
                reason_code=payload.get("reason_code"),
                event_time=payload.get("event_time"),
                source=str(payload.get("source", "manual")),
                event_message=payload.get("event_message"),
                raw_payload=payload.get("raw_payload"),
                carrier_name=payload.get("carrier_name"),
            )

        if operation == "sync":
            return self.sync_events_tool(db, events=payload.get("events") or [])

        if operation == "evaluate":
            return self.evaluate_alerts_tool(
                db,
                delivery_id=int(payload["delivery_id"]),
                send_alerts=bool(payload.get("send_alerts", False)),
            )

        raise ValueError(f"Unsupported delivery tracker operation: {operation}")
