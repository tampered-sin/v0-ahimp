from __future__ import annotations

from datetime import date
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.config import AgentTask
from agents.purchase_order_agent import PurchaseOrderAgent, build_purchase_order_payload
from database.db import Base
from database.models import (
    Batch,
    Department,
    InventoryStock,
    Item,
    PurchaseOrder,
    PurchaseOrderDetail,
    Supplier,
)


def _make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def _seed_minimum(db):
    db.add(Department(department_id=1, department_name="Pharmacy", location="A"))
    db.add(Item(item_id=1, item_name="Gloves", category="PPE", unit_type="box", reorder_point=100, safety_stock_level=120))
    db.add(
        Supplier(
            supplier_id=1,
            supplier_name="Prime Care",
            contact_email="supplier@example.com",
            avg_lead_time_days=5,
            reliability_score=0.9,
        )
    )
    db.add(Batch(item_id=1, supplier_id=1, purchase_price=10.0, quantity_received=1000))
    db.add(InventoryStock(item_id=1, batch_id=1, department_id=1, current_quantity=30))
    db.commit()


def test_purchase_order_execute_end_to_end():
    db = _make_db()
    _seed_minimum(db)

    agent = PurchaseOrderAgent()
    task = AgentTask(
        name="purchase_order_generation",
        description="generate and submit",
        payload=build_purchase_order_payload(item_id=1, supplier_id=1, risk_prob=0.9, submission_method="email"),
    )

    out = agent.run(task=task, context={"db": db})

    assert out["ok"] is True
    generated = out["result"]["generated"]
    submitted = out["result"]["submitted"]
    tracking = out["result"]["tracking"]

    assert generated["po_id"] >= 1
    assert generated["quantity"] > 0
    assert submitted["po_status"] in {"SUBMITTED", "PENDING_APPROVAL"}
    assert tracking["po_id"] == generated["po_id"]


def test_purchase_order_duplicate_prevention():
    db = _make_db()
    _seed_minimum(db)

    po = PurchaseOrder(supplier_id=1, order_date=date.today(), expected_delivery=date.today(), status="APPROVED")
    db.add(po)
    db.flush()
    db.add(
        PurchaseOrderDetail(
            po_id=int(po.po_id),
            item_id=1,
            quantity=50,
            unit_price=10.0,
            discount_pct=0.0,
            total_cost=500.0,
            created_by="test",
            approval_required=False,
            approval_status="APPROVED",
            submission_status="PENDING",
        )
    )
    db.commit()

    agent = PurchaseOrderAgent()
    with pytest.raises(ValueError):
        agent.generate_po_tool(
            db,
            item_id=1,
            supplier_id=1,
            risk_prob=0.8,
            created_by="test",
            discount_pct=0.0,
            budget_threshold=10000.0,
        )


def test_purchase_order_budget_approval_required():
    db = _make_db()
    _seed_minimum(db)

    agent = PurchaseOrderAgent()
    out = agent.generate_po_tool(
        db,
        item_id=1,
        supplier_id=1,
        risk_prob=0.95,
        created_by="test",
        discount_pct=0.0,
        budget_threshold=100.0,
    )

    assert out["approval_required"] is True
    assert out["status"] == "PENDING_APPROVAL"
