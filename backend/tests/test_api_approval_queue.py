from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

from api import approval_queue
from database.db import Base
from database.models import (
    Department,
    Item,
    PurchaseOrder,
    PurchaseOrderApproval,
    PurchaseOrderApprovalAudit,
    PurchaseOrderDetail,
    Supplier,
)


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
    app.include_router(approval_queue.router, prefix="/api")

    def _override_db():
        yield session

    app.dependency_overrides[approval_queue.get_db] = _override_db
    return app, session


def _seed_reference_data(session):
    session.add(Department(department_id=1, department_name="Pharmacy", location="A"))
    session.add(Item(item_id=1, item_name="Gloves", category="PPE", unit_type="box"))
    session.add(
        Supplier(
            supplier_id=1,
            supplier_name="Prime",
            contact_email="supplier@example.com",
            avg_lead_time_days=5,
            reliability_score=0.7,
        )
    )
    session.commit()


def _create_po_with_approval(
    session,
    *,
    approval_level: str,
    approval_status: str,
    due_at: datetime | None,
    escalation_required: bool,
) -> int:
    po_status = "PENDING_MANAGER_APPROVAL" if approval_status == "PENDING_MANAGER_REVIEW" else "PENDING_APPROVAL"
    po = PurchaseOrder(
        supplier_id=1,
        order_date=date.today(),
        expected_delivery=date.today() + timedelta(days=5),
        status=po_status,
    )
    session.add(po)
    session.flush()

    session.add(
        PurchaseOrderDetail(
            po_id=int(po.po_id),
            item_id=1,
            quantity=120,
            unit_price=100.0,
            discount_pct=0.0,
            total_cost=12000.0,
            created_by="tester",
            approval_required=True,
            approval_status=approval_status,
            submission_method=None,
            submission_status="PENDING",
            tracking_reference=f"PO-{po.po_id}",
        )
    )

    session.add(
        PurchaseOrderApproval(
            po_id=int(po.po_id),
            approval_level=approval_level,
            approval_status=approval_status,
            escalation_required=escalation_required,
            approval_reason="amount_requires_manual_review",
            score_breakdown={"total_cost": 12000.0},
            rule_snapshot={"auto_approve_limit": 5000.0},
            requested_at=datetime.now(tz=timezone.utc),
            due_at=due_at,
        )
    )

    session.add(
        PurchaseOrderApprovalAudit(
            po_id=int(po.po_id),
            event_type="CREATED",
            previous_status=None,
            new_status=approval_status,
            actor="tester",
            comment="created for test",
            metadata_json={"source": "unit-test"},
        )
    )

    session.commit()
    return int(po.po_id)


def test_approval_queue_list_and_detail(monkeypatch):
    app, session = _build_app_with_db()
    _seed_reference_data(session)
    po_id = _create_po_with_approval(
        session,
        approval_level="MANUAL",
        approval_status="PENDING_REVIEW",
        due_at=datetime.now(tz=timezone.utc) + timedelta(hours=6),
        escalation_required=False,
    )

    monkeypatch.setattr(approval_queue, "send_anomaly_alert", lambda **_: {"alert_id": 1})

    client = TestClient(app)
    list_resp = client.get("/api/approval-queue", params={"status": "PENDING_REVIEW", "limit": 10, "offset": 0})
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert payload["count"] == 1
    assert payload["items"][0]["po_id"] == po_id

    detail_resp = client.get(f"/api/approval-queue/{po_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["po_id"] == po_id
    assert detail["approval_status"] == "PENDING_REVIEW"
    assert len(detail["audit_trail"]) >= 1


def test_approval_decision_approve_updates_purchase_order(monkeypatch):
    app, session = _build_app_with_db()
    _seed_reference_data(session)
    po_id = _create_po_with_approval(
        session,
        approval_level="MANUAL",
        approval_status="PENDING_REVIEW",
        due_at=datetime.now(tz=timezone.utc) + timedelta(hours=6),
        escalation_required=False,
    )

    monkeypatch.setattr(approval_queue, "send_anomaly_alert", lambda **_: {"alert_id": 1})

    client = TestClient(app)
    decision_resp = client.post(
        f"/api/approval-queue/{po_id}/decision",
        json={
            "action": "approve",
            "reviewed_by": "procurement.user",
            "reviewer_role": "analyst",
            "comment": "approved after manual check",
        },
    )
    assert decision_resp.status_code == 200
    body = decision_resp.json()
    assert body["approval_status"] == "APPROVED"
    assert body["po_status"] == "APPROVED"

    approval_row = session.query(PurchaseOrderApproval).filter(PurchaseOrderApproval.po_id == po_id).first()
    detail_row = session.query(PurchaseOrderDetail).filter(PurchaseOrderDetail.po_id == po_id).first()
    po_row = session.query(PurchaseOrder).filter(PurchaseOrder.po_id == po_id).first()

    assert approval_row is not None
    assert detail_row is not None
    assert po_row is not None
    assert approval_row.approval_status == "APPROVED"
    assert detail_row.approval_required is False
    assert detail_row.approval_status == "APPROVED"
    assert po_row.status == "APPROVED"


def test_manager_approval_requires_manager_role(monkeypatch):
    app, session = _build_app_with_db()
    _seed_reference_data(session)
    po_id = _create_po_with_approval(
        session,
        approval_level="MANAGER",
        approval_status="PENDING_MANAGER_REVIEW",
        due_at=datetime.now(tz=timezone.utc) + timedelta(hours=6),
        escalation_required=True,
    )

    monkeypatch.setattr(approval_queue, "send_anomaly_alert", lambda **_: {"alert_id": 1})

    client = TestClient(app)
    denied = client.post(
        f"/api/approval-queue/{po_id}/decision",
        json={
            "action": "approve",
            "reviewed_by": "procurement.user",
            "reviewer_role": "analyst",
            "comment": "attempt",
        },
    )
    assert denied.status_code == 403

    allowed = client.post(
        f"/api/approval-queue/{po_id}/decision",
        json={
            "action": "approve",
            "reviewed_by": "manager.user",
            "reviewer_role": "manager",
            "comment": "approved by manager",
        },
    )
    assert allowed.status_code == 200
    assert allowed.json()["approval_status"] == "APPROVED"


def test_approval_timeout_processing_endpoint(monkeypatch):
    app, session = _build_app_with_db()
    _seed_reference_data(session)
    po_id = _create_po_with_approval(
        session,
        approval_level="MANUAL",
        approval_status="PENDING_REVIEW",
        due_at=datetime.now(tz=timezone.utc) - timedelta(hours=1),
        escalation_required=False,
    )

    monkeypatch.setattr(approval_queue, "send_anomaly_alert", lambda **_: {"alert_id": 1})

    client = TestClient(app)
    timeout_resp = client.post("/api/approval-queue/auto-timeout")
    assert timeout_resp.status_code == 200
    payload = timeout_resp.json()
    assert payload["count"] == 1
    assert payload["items"][0]["po_id"] == po_id
    assert payload["items"][0]["new_status"] == "AUTO_APPROVED_TIMEOUT"

    approval_row = session.query(PurchaseOrderApproval).filter(PurchaseOrderApproval.po_id == po_id).first()
    detail_row = session.query(PurchaseOrderDetail).filter(PurchaseOrderDetail.po_id == po_id).first()
    po_row = session.query(PurchaseOrder).filter(PurchaseOrder.po_id == po_id).first()

    assert approval_row is not None
    assert detail_row is not None
    assert po_row is not None
    assert approval_row.approval_status == "AUTO_APPROVED_TIMEOUT"
    assert detail_row.approval_status == "AUTO_APPROVED_TIMEOUT"
    assert detail_row.approval_required is False
    assert po_row.status == "APPROVED"
