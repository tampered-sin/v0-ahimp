from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.config import AgentTask
from agents.supply_chain_agent import SupplyChainAgent, build_supply_chain_payload
from database.db import Base
from database.models import Batch, InventoryStock, Item, Supplier


def _make_db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def _seed_search_suppliers_fixtures(db):
    item = Item(item_id=1, item_name="Paracetamol 500mg", category="General", unit_type="strip")
    db.add(item)

    suppliers = [
        Supplier(
            supplier_id=1,
            supplier_name="Alpha Medical",
            avg_lead_time_days=2,
            reliability_score=0.92,
        ),
        Supplier(
            supplier_id=2,
            supplier_name="Budget Pharma",
            avg_lead_time_days=6,
            reliability_score=0.55,
        ),
    ]
    db.add_all(suppliers)

    batch_1 = Batch(item_id=1, supplier_id=1, purchase_price=3.4, quantity_received=400)
    batch_2 = Batch(item_id=1, supplier_id=2, purchase_price=2.9, quantity_received=600)
    db.add_all([batch_1, batch_2])
    db.flush()

    db.add_all(
        [
            InventoryStock(item_id=1, batch_id=batch_1.batch_id, department_id=1, current_quantity=250),
            InventoryStock(item_id=1, batch_id=batch_2.batch_id, department_id=1, current_quantity=500),
        ]
    )
    db.commit()


def test_search_suppliers_tool_alias_and_filters(monkeypatch):
    db = _make_db_session()
    _seed_search_suppliers_fixtures(db)
    agent = SupplyChainAgent()

    monkeypatch.setenv("MEDICINE_FUZZY_THRESHOLD", "0.6")

    result = agent.search_suppliers_tool(
        db,
        medicine_name="Acetaminophen",
        quantity=200,
        location="Bangalore",
        max_distance_km=50,
        min_reliability=0.6,
        supplier_overrides=[
            {"supplier_id": 1, "distance_km": 18},
            {"supplier_id": 2, "distance_km": 22},
        ],
    )

    assert len(result) == 1
    assert result[0]["supplier_id"] == 1
    assert result[0]["item_name"] == "Paracetamol 500mg"
    assert result[0]["reliability_score"] >= 0.6


def test_supply_chain_execute_without_auto_purchase(monkeypatch):
    agent = SupplyChainAgent()

    def _execute(name, *args, **kwargs):
        if name == "check_stockout_risk_tool":
            return [{"item_id": 1, "item_name": "Gloves", "risk_prob": 0.82}]
        if name == "search_suppliers_tool":
            return [{"supplier_id": 2, "name": "Prime Care", "search_score": 0.88}]
        if name == "score_suppliers_tool":
            return {
                "suppliers": [
                    {
                        "supplier_id": 2,
                        "supplier_name": "Prime Care",
                        "score": 89.5,
                        "breakdown": {"reliability": 95.0},
                    }
                ]
            }
        if name == "compare_quotes_tool":
            return [
                {
                    "supplier_id": 2,
                    "supplier_name": "Prime Care",
                    "score": 89.5,
                    "breakdown": {"reliability": 95.0},
                    "decision_metrics": {
                        "composite_score": 0.84,
                    },
                }
            ]
        if name == "decide_order_action_tool":
            return "AUTO_ORDER"
        if name == "build_dual_source_plan_tool":
            return None
        if name == "calculate_order_qty_tool":
            return 140
        raise AssertionError(f"Unexpected tool: {name}")

    monkeypatch.setattr(agent.registry, "execute", _execute)

    task = AgentTask(
        name="supply_chain_monitor",
        description="stockout check",
        payload=build_supply_chain_payload(risk_threshold=0.7, auto_purchase=False),
    )

    out = agent.execute(task=task, context={"db": object()})

    assert out["auto_purchase"] is False
    assert out["cadence_hours"] == 1
    assert out["items_evaluated"] == 1
    assert out["decisions"][0]["action"] == "AUTO_ORDER"
    assert out["decisions"][0]["created_po"] is None
    assert out["escalations"] == []
    assert out["cycle_duration_sec"] >= 0
    assert out["sla_under_30s"] is True


def test_supply_chain_execute_with_auto_purchase(monkeypatch):
    agent = SupplyChainAgent()

    def _execute(name, *args, **kwargs):
        if name == "check_stockout_risk_tool":
            return [{"item_id": 3, "item_name": "Masks", "risk_prob": 0.9}]
        if name == "search_suppliers_tool":
            return [{"supplier_id": 1, "name": "Alpha Medical", "search_score": 0.92}]
        if name == "score_suppliers_tool":
            return {
                "suppliers": [
                    {
                        "supplier_id": 1,
                        "supplier_name": "Alpha Medical",
                        "score": 90.2,
                        "breakdown": {"reliability": 96.0},
                    }
                ]
            }
        if name == "compare_quotes_tool":
            return [
                {
                    "supplier_id": 1,
                    "supplier_name": "Alpha Medical",
                    "score": 90.2,
                    "breakdown": {"reliability": 96.0},
                    "decision_metrics": {
                        "composite_score": 0.86,
                    },
                }
            ]
        if name == "decide_order_action_tool":
            return "AUTO_ORDER"
        if name == "build_dual_source_plan_tool":
            return None
        if name == "calculate_order_qty_tool":
            return 200
        if name == "create_po_tool":
            return SimpleNamespace(
                po_id=44,
                supplier_id=1,
                order_date=date.today(),
                expected_delivery=date.today() + timedelta(days=7),
                status="AUTO_CREATED",
            )
        if name == "send_to_supplier_tool":
            return {"po_id": 44, "channel": "email", "status": "queued"}
        if name == "track_delivery_tool":
            return {"po_id": 44, "status": "AUTO_CREATED"}
        raise AssertionError(f"Unexpected tool: {name}")

    monkeypatch.setattr(agent.registry, "execute", _execute)

    task = AgentTask(
        name="supply_chain_monitor",
        description="auto purchase",
        payload=build_supply_chain_payload(risk_threshold=0.7, auto_purchase=True),
    )

    out = agent.execute(task=task, context={"db": object()})

    assert out["auto_purchase"] is True
    assert out["decisions"][0]["action"] == "AUTO_ORDER"
    assert out["decisions"][0]["created_po"]["po_id"] == 44
    assert out["decisions"][0]["dispatch"]["channel"] == "email"
    assert out["sla_under_30s"] is True


def test_supply_chain_critical_item_does_not_auto_purchase(monkeypatch):
    agent = SupplyChainAgent()

    def _execute(name, *args, **kwargs):
        if name == "check_stockout_risk_tool":
            return [{"item_id": 7, "item_name": "Insulin", "risk_prob": 0.93}]
        if name == "search_suppliers_tool":
            return [
                {"supplier_id": 1, "name": "Alpha Medical", "search_score": 0.9},
                {"supplier_id": 2, "name": "Prime Care", "search_score": 0.82},
            ]
        if name == "score_suppliers_tool":
            return {
                "suppliers": [
                    {
                        "supplier_id": 1,
                        "supplier_name": "Alpha Medical",
                        "score": 91.0,
                        "breakdown": {"reliability": 97.0},
                    },
                    {
                        "supplier_id": 2,
                        "supplier_name": "Prime Care",
                        "score": 86.0,
                        "breakdown": {"reliability": 92.0},
                    },
                ]
            }
        if name == "compare_quotes_tool":
            return [
                {
                    "supplier_id": 1,
                    "supplier_name": "Alpha Medical",
                    "score": 91.0,
                    "breakdown": {"reliability": 97.0},
                    "decision_metrics": {
                        "composite_score": 0.9,
                    },
                },
                {
                    "supplier_id": 2,
                    "supplier_name": "Prime Care",
                    "score": 86.0,
                    "breakdown": {"reliability": 92.0},
                    "decision_metrics": {
                        "composite_score": 0.78,
                    },
                },
            ]
        if name == "decide_order_action_tool":
            composite_score = float(args[0])
            is_critical = bool(args[1])
            assert composite_score == 0.9
            assert is_critical is True
            return "SUGGEST_HUMAN_APPROVAL"
        if name == "build_dual_source_plan_tool":
            compared_suppliers = args[0]
            total_qty = int(args[1])
            assert total_qty == 120
            assert len(compared_suppliers) == 2
            return {
                "strategy": "DUAL_SOURCE",
                "split": {"primary_pct": 60, "secondary_pct": 40},
                "orders": [
                    {"supplier_id": 1, "quantity": 72},
                    {"supplier_id": 2, "quantity": 48},
                ],
            }
        if name == "calculate_order_qty_tool":
            return 120
        if name in {"create_po_tool", "send_to_supplier_tool", "track_delivery_tool"}:
            raise AssertionError("Auto-purchase tools should not be called for critical items")
        raise AssertionError(f"Unexpected tool: {name}")

    monkeypatch.setattr(agent.registry, "execute", _execute)

    task = AgentTask(
        name="supply_chain_monitor",
        description="critical medicines require approval",
        payload=build_supply_chain_payload(
            risk_threshold=0.7,
            auto_purchase=True,
            critical_item_ids=[7],
        ),
    )

    out = agent.execute(task=task, context={"db": object()})

    assert out["auto_purchase"] is True
    assert out["decisions"][0]["action"] == "SUGGEST_HUMAN_APPROVAL"
    assert out["decisions"][0]["is_critical"] is True
    assert out["decisions"][0]["created_po"] is None
    assert out["decisions"][0]["dual_source_plan"]["strategy"] == "DUAL_SOURCE"
    assert len(out["decisions"][0]["dual_source_plan"]["orders"]) == 2


def test_supply_chain_escalates_when_no_suppliers(monkeypatch):
    agent = SupplyChainAgent()

    def _execute(name, *args, **kwargs):
        if name == "check_stockout_risk_tool":
            return [{"item_id": 11, "item_name": "Epinephrine", "risk_prob": 0.96, "days_until_stockout": 1}]
        if name == "search_suppliers_tool":
            return []
        if name == "score_suppliers_tool":
            return {"suppliers": []}
        if name == "escalate_to_human_tool":
            return {
                "escalation": {"escalation_id": 501, "priority": "CRITICAL"},
                "alert": {"sent": True, "channels": ["log"]},
            }
        raise AssertionError(f"Unexpected tool: {name}")

    monkeypatch.setattr(agent.registry, "execute", _execute)

    task = AgentTask(
        name="supply_chain_monitor",
        description="escalate missing suppliers",
        payload=build_supply_chain_payload(
            risk_threshold=0.7,
            auto_purchase=True,
            critical_item_ids=[11],
        ),
    )

    out = agent.execute(task=task, context={"db": object()})

    assert out["items_evaluated"] == 1
    assert out["decisions"] == []
    assert len(out["escalations"]) == 1
    assert out["escalations"][0]["ticket"]["escalation_id"] == 501
