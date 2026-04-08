from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.config import AgentTask
from agents.delivery_tracker import DeliveryTrackerAgent, build_delivery_tracker_payload
from database.db import Base
from database.models import PurchaseOrder, PurchaseOrderDetail, Supplier


def _make_db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def _seed_purchase_order(db):
    db.add(Supplier(supplier_id=1, supplier_name="Prime", contact_email="supplier@example.com"))
    po = PurchaseOrder(
        supplier_id=1,
        order_date=date.today(),
        expected_delivery=date.today() + timedelta(days=2),
        status="SUBMITTED",
    )
    db.add(po)
    db.flush()
    db.add(
        PurchaseOrderDetail(
            po_id=int(po.po_id),
            item_id=1,
            quantity=20,
            unit_price=10.0,
            discount_pct=0.0,
            total_cost=200.0,
            created_by="tester",
            approval_required=False,
            approval_status="APPROVED",
            submission_method="EMAIL",
            submission_status="EMAIL_QUEUED",
            tracking_reference=f"PO-{po.po_id}",
        )
    )
    db.commit()
    return int(po.po_id)


def test_delivery_tracker_create_update_and_deliver(monkeypatch):
    db = _make_db_session()
    po_id = _seed_purchase_order(db)

    monkeypatch.setattr(
        "agents.delivery_tracker.send_anomaly_alert",
        lambda subject, body, recipients=None, severity="RED": {
            "sent": True,
            "severity": severity,
            "channels": ["log"],
        },
    )

    agent = DeliveryTrackerAgent()

    create_out = agent.run(
        AgentTask(
            name="delivery_tracking",
            description="create",
            payload=build_delivery_tracker_payload(operation="create", po_id=po_id),
        ),
        context={"db": db},
    )
    assert create_out["ok"] is True
    delivery_id = create_out["result"]["delivery_id"]

    update_confirmed = agent.run(
        AgentTask(
            name="delivery_tracking",
            description="update confirmed",
            payload=build_delivery_tracker_payload(
                operation="update",
                delivery_id=delivery_id,
                new_status="confirmed",
                source="manual",
            ),
        ),
        context={"db": db},
    )
    assert update_confirmed["ok"] is True
    assert update_confirmed["result"]["applied"] is True
    assert update_confirmed["result"]["status"] == "CONFIRMED"

    update_in_transit = agent.run(
        AgentTask(
            name="delivery_tracking",
            description="update in transit",
            payload=build_delivery_tracker_payload(
                operation="update",
                delivery_id=delivery_id,
                new_status="in_transit",
                source="manual",
            ),
        ),
        context={"db": db},
    )
    assert update_in_transit["ok"] is True
    assert update_in_transit["result"]["status"] == "IN_TRANSIT"

    update_delivered = agent.run(
        AgentTask(
            name="delivery_tracking",
            description="update delivered",
            payload=build_delivery_tracker_payload(
                operation="update",
                delivery_id=delivery_id,
                new_status="delivered",
                source="manual",
            ),
        ),
        context={"db": db},
    )
    assert update_delivered["ok"] is True
    assert update_delivered["result"]["status"] == "DELIVERED"


def test_delivery_tracker_rejects_invalid_transition():
    db = _make_db_session()
    po_id = _seed_purchase_order(db)
    agent = DeliveryTrackerAgent()

    created = agent.create_delivery_tool(db, po_id=po_id)
    delivery_id = int(created["delivery_id"])

    out = agent.apply_status_event_tool(
        db,
        delivery_id=delivery_id,
        external_status_code="DELIVERED",
        source="manual",
    )
    assert out["applied"] is False
    assert out["reason"] == "invalid_transition"


def test_delivery_tracker_sync_deduplicates_events(monkeypatch):
    db = _make_db_session()
    po_id = _seed_purchase_order(db)
    agent = DeliveryTrackerAgent()

    created = agent.create_delivery_tool(db, po_id=po_id)
    tracking_reference = created["tracking_reference"]

    monkeypatch.setattr(
        "agents.delivery_tracker.send_anomaly_alert",
        lambda subject, body, recipients=None, severity="RED": {"sent": True},
    )

    event_time = datetime.now(tz=timezone.utc).isoformat()
    out = agent.sync_events_tool(
        db,
        events=[
            {
                "tracking_reference": tracking_reference,
                "external_status_code": "CONFIRMED",
                "event_time": event_time,
                "source": "supplier_api",
            },
            {
                "tracking_reference": tracking_reference,
                "external_status_code": "CONFIRMED",
                "event_time": event_time,
                "source": "supplier_api",
            },
        ],
    )

    assert out["received"] == 2
    assert out["applied"] == 1
    assert out["duplicates"] == 1
