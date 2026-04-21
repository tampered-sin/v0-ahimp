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

from api import deliveries
from database.db import Base
from database.models import PurchaseOrder, PurchaseOrderDetail, Supplier


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
    app.include_router(deliveries.router, prefix="/api")

    def _override_db():
        yield session

    app.dependency_overrides[deliveries.get_db] = _override_db
    return app, session


def _seed_po(session):
    session.add(Supplier(supplier_id=1, supplier_name="Prime", contact_email="supplier@example.com"))
    po = PurchaseOrder(
        supplier_id=1,
        order_date=date.today(),
        expected_delivery=date.today(),
        status="SUBMITTED",
    )
    session.add(po)
    session.flush()
    session.add(
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
    session.commit()
    return int(po.po_id)


def test_api_deliveries_create_list_update_and_sync():
    app, session = _build_app_with_db()
    po_id = _seed_po(session)
    client = TestClient(app)

    create_resp = client.post("/api/deliveries/status", json={"po_id": po_id})
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["po_id"] == po_id
    delivery_id = created["delivery_id"]
    tracking_reference = created["tracking_reference"]

    list_resp = client.get("/api/deliveries/status")
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] >= 1

    update_confirmed = client.patch(
        f"/api/deliveries/status/{delivery_id}",
        json={"new_status": "confirmed", "source": "manual"},
    )
    assert update_confirmed.status_code == 200
    assert update_confirmed.json()["status"] == "CONFIRMED"

    sync_resp = client.post(
        "/api/deliveries/sync",
        json={
            "events": [
                {
                    "tracking_reference": tracking_reference,
                    "external_status_code": "IN_TRANSIT",
                    "source": "supplier_api",
                }
            ]
        },
    )
    assert sync_resp.status_code == 200
    assert sync_resp.json()["applied"] == 1


def test_api_deliveries_invalid_transition_returns_conflict():
    app, session = _build_app_with_db()
    po_id = _seed_po(session)
    client = TestClient(app)

    create_resp = client.post("/api/deliveries/status", json={"po_id": po_id})
    delivery_id = create_resp.json()["delivery_id"]

    invalid = client.patch(
        f"/api/deliveries/status/{delivery_id}",
        json={"new_status": "DELIVERED", "source": "manual"},
    )
    assert invalid.status_code == 409
