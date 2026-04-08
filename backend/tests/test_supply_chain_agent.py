from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.config import AgentTask
from agents.supply_chain_agent import SupplyChainAgent, build_supply_chain_payload


def test_supply_chain_execute_without_auto_purchase(monkeypatch):
    agent = SupplyChainAgent()

    def _execute(name, *args, **kwargs):
        if name == "check_stockout_risk_tool":
            return [{"item_id": 1, "item_name": "Gloves", "risk_prob": 0.82}]
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
    assert out["decisions"][0]["created_po"] is None
    assert out["cycle_duration_sec"] >= 0
    assert out["sla_under_30s"] is True


def test_supply_chain_execute_with_auto_purchase(monkeypatch):
    agent = SupplyChainAgent()

    def _execute(name, *args, **kwargs):
        if name == "check_stockout_risk_tool":
            return [{"item_id": 3, "item_name": "Masks", "risk_prob": 0.9}]
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
    assert out["decisions"][0]["created_po"]["po_id"] == 44
    assert out["decisions"][0]["dispatch"]["channel"] == "email"
    assert out["sla_under_30s"] is True
