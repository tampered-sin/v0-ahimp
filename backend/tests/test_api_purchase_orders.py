from __future__ import annotations

from datetime import date
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

from api import purchase_orders
from database.db import Base
from database.models import Department, Item, PurchaseOrder, PurchaseOrderDetail, Supplier


def _build_app_with_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()

    app = FastAPI()
    app.include_router(purchase_orders.router, prefix="/api")

    def _override_db():
        yield session

    app.dependency_overrides[purchase_orders.get_db] = _override_db
    return app, session


def _seed_basic(session):
    session.add(Department(department_id=1, department_name="Pharmacy", location="A"))
    session.add(Item(item_id=1, item_name="Gloves", category="PPE", unit_type="box"))
    session.add(Supplier(supplier_id=1, supplier_name="Prime", contact_email="supplier@example.com", avg_lead_time_days=5))
    session.commit()


def test_create_and_list_purchase_orders(monkeypatch):
    app, session = _build_app_with_db()
    _seed_basic(session)

    monkeypatch.setattr(
        purchase_orders,
        "_agent_run",
        lambda payload, db: {
            "ok": True,
            "agent": "purchase-order-agent",
            "result": {"generated": {"po_id": 1}, "submitted": {}, "tracking": {}},
        },
    )

    client = TestClient(app)
    create_resp = client.post("/api/purchase-orders", json={"item_id": 1, "supplier_id": 1})
    assert create_resp.status_code == 200

    po = PurchaseOrder(po_id=1, supplier_id=1, order_date=date.today(), expected_delivery=date.today(), status="SUBMITTED")
    session.add(po)
    session.flush()
    session.add(
        PurchaseOrderDetail(
            po_id=1,
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
            tracking_reference="PO-1",
        )
    )
    session.commit()

    list_resp = client.get("/api/purchase-orders")
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] >= 1


def test_get_update_submit_and_tracking_routes(monkeypatch):
    app, session = _build_app_with_db()
    _seed_basic(session)

    po = PurchaseOrder(po_id=5, supplier_id=1, order_date=date.today(), expected_delivery=date.today(), status="APPROVED")
    session.add(po)
    session.flush()
    session.add(
        PurchaseOrderDetail(
            po_id=5,
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
            tracking_reference="PO-5",
        )
    )
    session.commit()

    monkeypatch.setattr(
        "agents.purchase_order_agent.PurchaseOrderAgent.submit_po_tool",
        lambda self, db, po_id, method, supplier_api_url=None: {
            "po_id": po_id,
            "method": method,
            "submission_status": "EMAIL_QUEUED",
            "po_status": "SUBMITTED",
        },
    )
    monkeypatch.setattr(
        "agents.purchase_order_agent.PurchaseOrderAgent.track_po_tool",
        lambda self, db, po_id: {"po_id": po_id, "status": "SUBMITTED", "delayed": False},
    )

    client = TestClient(app)

    get_resp = client.get("/api/purchase-orders/5")
    assert get_resp.status_code == 200
    assert get_resp.json()["po_id"] == 5

    patch_resp = client.patch("/api/purchase-orders/5/status", json={"status": "delivered"})
    assert patch_resp.status_code == 200
    assert "DELIVERED" in patch_resp.json()["status"]

    submit_resp = client.post("/api/purchase-orders/5/submit", json={"method": "email"})
    assert submit_resp.status_code == 200
    assert submit_resp.json()["po_id"] == 5

    tracking_resp = client.get("/api/purchase-orders/5/tracking")
    assert tracking_resp.status_code == 200
    assert tracking_resp.json()["po_id"] == 5
