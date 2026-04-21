from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from api import supply_chain


def _fake_get_db():
    class _DB:
        pass

    yield _DB()


def test_supply_chain_at_risk_route(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    calls = []

    def _capture_log(db, **kwargs):
        calls.append(kwargs)
        return {"log_id": 1}

    monkeypatch.setattr(supply_chain, "create_agent_log", _capture_log)

    monkeypatch.setattr(
        supply_chain,
        "_run_supply_chain_task",
        lambda payload, db, auto_purchase: {
            "ok": True,
            "agent": "supply-chain-agent",
            "result": {"auto_purchase": auto_purchase, "decisions": []},
        },
    )

    client = TestClient(app)
    resp = client.post("/api/agents/supply-chain/at-risk", json={"risk_threshold": 0.75, "max_items": 5})

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert len(calls) == 1
    assert calls[0]["task_description"] == "supply_chain_at_risk"
    assert calls[0]["status"] == "succeeded"
    assert "session_id" in calls[0]["result"]
    assert calls[0]["result"]["tool_called"] == "run_supply_chain_task"


def test_supply_chain_auto_purchase_failure(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    monkeypatch.setattr(
        supply_chain,
        "_run_supply_chain_task",
        lambda payload, db, auto_purchase: {"ok": False, "error": "failed"},
    )

    client = TestClient(app)
    resp = client.post("/api/agents/supply-chain/auto-purchase", json={"risk_threshold": 0.8, "max_items": 3})

    assert resp.status_code == 500


def test_supply_chain_search_suppliers_route_success(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    monkeypatch.setattr(
        supply_chain,
        "_search_suppliers",
        lambda payload, db: {
            "ok": True,
            "agent": "supply-chain-agent",
            "result": {
                "query": {"medicine_name": payload.medicine_name},
                "suppliers": [{"supplier_id": 1, "name": "Alpha Medical"}],
            },
        },
    )

    client = TestClient(app)
    resp = client.post(
        "/api/agents/supply-chain/search-suppliers",
        json={
            "medicine_name": "Paracetamol 500mg",
            "quantity": 250,
            "location": "Bangalore",
            "max_distance_km": 60,
            "min_reliability": 0.7,
            "supplier_overrides": [{"supplier_id": 1, "distance_km": 12}],
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["result"]["suppliers"][0]["supplier_id"] == 1


def test_supply_chain_search_suppliers_route_value_error(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    def _raise(*args, **kwargs):
        raise ValueError("invalid supplier search")

    monkeypatch.setattr(supply_chain, "_search_suppliers", _raise)

    client = TestClient(app)
    resp = client.post(
        "/api/agents/supply-chain/search-suppliers",
        json={
            "medicine_name": "Paracetamol 500mg",
            "quantity": 250,
        },
    )

    assert resp.status_code == 400


def test_supply_chain_escalations_list_route_success(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    monkeypatch.setattr(
        supply_chain,
        "list_escalations",
        lambda db, status, limit, offset: {
            "count": 1,
            "records": [{"escalation_id": 10, "status": status}],
        },
    )

    client = TestClient(app)
    resp = client.get("/api/agents/supply-chain/escalations?status=OPEN&limit=25&offset=0")

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["records"][0]["status"] == "OPEN"


def test_supply_chain_escalations_list_route_bad_status():
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    client = TestClient(app)
    resp = client.get("/api/agents/supply-chain/escalations?status=INVALID")

    assert resp.status_code == 400


def test_supply_chain_escalation_resolve_route_success(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    monkeypatch.setattr(
        supply_chain,
        "resolve_escalation",
        lambda db, escalation_id, action, resolution_note, resolved_by: {
            "escalation_id": escalation_id,
            "status": action,
            "context": {"resolution_note": resolution_note, "resolved_by": resolved_by},
        },
    )

    client = TestClient(app)
    resp = client.post(
        "/api/agents/supply-chain/escalations/42/resolve",
        json={
            "action": "RESOLVED",
            "resolution_note": "Procurement approved alternate vendor",
            "resolved_by": "procurement.lead",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["escalation_id"] == 42
    assert body["status"] == "RESOLVED"


def test_supply_chain_escalation_resolve_route_not_found(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    def _raise(*args, **kwargs):
        raise ValueError("Escalation not found")

    monkeypatch.setattr(supply_chain, "resolve_escalation", _raise)

    client = TestClient(app)
    resp = client.post(
        "/api/agents/supply-chain/escalations/999/resolve",
        json={
            "action": "DISMISSED",
            "resolution_note": "False positive from stale signal",
            "resolved_by": "procurement.lead",
        },
    )

    assert resp.status_code == 404


def test_supply_chain_audit_traces_route_success(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    monkeypatch.setattr(
        supply_chain,
        "list_agent_logs",
        lambda db, agent_name=None, status=None, level=None, search=None, limit=100, offset=0: {
            "count": 1,
            "records": [
                {
                    "log_id": 7,
                    "task_description": "supply_chain_at_risk",
                    "status": "succeeded",
                    "created_at": "2026-04-08T10:00:00+00:00",
                    "result": {
                        "session_id": "abc",
                        "tool_called": "run_supply_chain_task",
                        "input_payload": {"risk_threshold": 0.7},
                        "output_payload": {"ok": True},
                        "reasoning_trace": [{"step": 1, "type": "decision"}],
                        "timestamp": "2026-04-08T10:00:01+00:00",
                    },
                    "errors": None,
                }
            ],
        },
    )

    client = TestClient(app)
    resp = client.get("/api/agents/supply-chain/audit-traces?status=succeeded&limit=20&offset=0")

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["audit_policy"]["append_only"] is True
    assert "update" in body["audit_policy"]["disallowed_operations"]
    assert body["records"][0]["session_id"] == "abc"
    assert body["records"][0]["tool_called"] == "run_supply_chain_task"
    assert len(body["records"][0]["reasoning_trace"]) == 1


def test_supply_chain_audit_traces_route_csv_export(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    monkeypatch.setattr(
        supply_chain,
        "list_agent_logs",
        lambda db, agent_name=None, status=None, level=None, search=None, limit=100, offset=0: {
            "count": 1,
            "records": [
                {
                    "log_id": 7,
                    "task_description": "supply_chain_at_risk",
                    "status": "succeeded",
                    "created_at": "2026-04-08T10:00:00+00:00",
                    "result": {
                        "session_id": "abc",
                        "tool_called": "run_supply_chain_task",
                        "input_payload": {"risk_threshold": 0.7},
                        "output_payload": {"ok": True},
                        "reasoning_trace": [{"step": 1, "type": "decision"}],
                        "timestamp": "2026-04-08T10:00:01+00:00",
                    },
                    "errors": None,
                }
            ],
        },
    )

    client = TestClient(app)
    resp = client.get("/api/agents/supply-chain/audit-traces?export=csv&limit=20&offset=0")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "log_id,created_at,task_description,status,session_id,tool_called" in resp.text
    assert "supply_chain_at_risk" in resp.text


def test_supply_chain_audit_traces_route_invalid_export(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    monkeypatch.setattr(
        supply_chain,
        "list_agent_logs",
        lambda db, agent_name=None, status=None, level=None, search=None, limit=100, offset=0: {
            "count": 0,
            "records": [],
        },
    )

    client = TestClient(app)
    resp = client.get("/api/agents/supply-chain/audit-traces?export=xml")

    assert resp.status_code == 400


def test_supply_chain_audit_trace_explain_success_by_session_id(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    monkeypatch.setattr(
        supply_chain,
        "list_agent_logs",
        lambda db, agent_name=None, status=None, level=None, search=None, limit=100, offset=0: {
            "count": 1,
            "records": [
                {
                    "log_id": 7,
                    "task_description": "supply_chain_at_risk",
                    "status": "succeeded",
                    "created_at": "2026-04-08T10:00:00+00:00",
                    "result": {
                        "session_id": "abc-123",
                        "tool_called": "run_supply_chain_task",
                        "input_payload": {"risk_threshold": 0.7},
                        "output_payload": {"ok": True},
                        "reasoning_trace": [
                            {
                                "step": 1,
                                "type": "decision",
                                "item_id": 11,
                                "action": "SUGGEST_HUMAN_APPROVAL",
                                "reason": "critical medicine",
                            }
                        ],
                        "timestamp": "2026-04-08T10:00:01+00:00",
                    },
                    "errors": None,
                }
            ],
        },
    )

    client = TestClient(app)
    resp = client.get("/api/agents/supply-chain/audit-traces/explain?session_id=abc-123")

    assert resp.status_code == 200
    body = resp.json()
    assert body["audit_policy"]["append_only"] is True
    assert body["session_id"] == "abc-123"
    assert "critical medicine" in body["human_explanation"]


def test_supply_chain_audit_trace_explain_requires_identifier():
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    client = TestClient(app)
    resp = client.get("/api/agents/supply-chain/audit-traces/explain")

    assert resp.status_code == 400


def test_supply_chain_audit_trace_explain_not_found(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    monkeypatch.setattr(
        supply_chain,
        "list_agent_logs",
        lambda db, agent_name=None, status=None, level=None, search=None, limit=100, offset=0: {
            "count": 0,
            "records": [],
        },
    )

    client = TestClient(app)
    resp = client.get("/api/agents/supply-chain/audit-traces/explain?log_id=99")

    assert resp.status_code == 404


def test_supply_chain_audit_summary_filters(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    monkeypatch.setattr(
        supply_chain,
        "list_agent_logs",
        lambda db, agent_name=None, status=None, level=None, search=None, limit=100, offset=0: {
            "count": 1,
            "records": [
                {
                    "log_id": 30,
                    "task_description": "supply_chain_auto_purchase",
                    "status": "succeeded",
                    "created_at": "2026-04-08T10:00:00+00:00",
                    "result": {
                        "session_id": "session-30",
                        "tool_called": "run_supply_chain_task",
                        "output_payload": {
                            "result": {
                                "decisions": [
                                    {
                                        "item_id": 7,
                                        "item_name": "Insulin",
                                        "action": "SUGGEST_HUMAN_APPROVAL",
                                        "reason": "critical medicine",
                                        "risk_prob": 0.93,
                                    },
                                    {
                                        "item_id": 9,
                                        "item_name": "Paracetamol 500mg",
                                        "action": "AUTO_ORDER",
                                        "reason": "high confidence",
                                        "risk_prob": 0.82,
                                    },
                                ],
                                "escalations": [],
                            }
                        },
                    },
                    "errors": None,
                }
            ],
        },
    )

    client = TestClient(app)
    resp = client.get(
        "/api/agents/supply-chain/audit-summary?decision_type=AUTO_ORDER&medicine=Paracetamol"
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["audit_policy"]["append_only"] is True
    assert body["count"] == 1
    assert body["records"][0]["decision_type"] == "AUTO_ORDER"
    assert "AUTO_ORDER" in body["counts_by_type"]


def test_supply_chain_audit_summary_bad_date_range():
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    client = TestClient(app)
    resp = client.get(
        "/api/agents/supply-chain/audit-summary?from_ts=2026-04-09T00:00:00Z&to_ts=2026-04-08T00:00:00Z"
    )

    assert resp.status_code == 400


def test_supply_chain_audit_traces_route_date_range_filter(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    monkeypatch.setattr(
        supply_chain,
        "list_agent_logs",
        lambda db, agent_name=None, status=None, level=None, search=None, limit=100, offset=0: {
            "count": 2,
            "records": [
                {
                    "log_id": 1,
                    "task_description": "supply_chain_at_risk",
                    "status": "succeeded",
                    "created_at": "2026-04-07T10:00:00+00:00",
                    "result": {"session_id": "old", "reasoning_trace": []},
                    "errors": None,
                },
                {
                    "log_id": 2,
                    "task_description": "supply_chain_at_risk",
                    "status": "succeeded",
                    "created_at": "2026-04-08T10:00:00+00:00",
                    "result": {"session_id": "new", "reasoning_trace": []},
                    "errors": None,
                },
            ],
        },
    )

    client = TestClient(app)
    resp = client.get(
        "/api/agents/supply-chain/audit-traces?from_ts=2026-04-08T00:00:00Z&to_ts=2026-04-08T23:59:59Z"
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["records"]) == 1
    assert body["records"][0]["log_id"] == 2


def test_supply_chain_audit_traces_route_invalid_date(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    monkeypatch.setattr(
        supply_chain,
        "list_agent_logs",
        lambda db, agent_name=None, status=None, level=None, search=None, limit=100, offset=0: {
            "count": 0,
            "records": [],
        },
    )

    client = TestClient(app)
    resp = client.get("/api/agents/supply-chain/audit-traces?from_ts=not-a-date")

    assert resp.status_code == 400


def test_supply_chain_routes_api_key_auth(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    monkeypatch.setenv("AGENTS_API_KEY", "test-key")
    monkeypatch.setattr(
        supply_chain,
        "_search_suppliers",
        lambda payload, db: {"ok": True, "result": {"suppliers": []}},
    )

    client = TestClient(app)

    unauthorized = client.post(
        "/api/agents/supply-chain/search-suppliers",
        json={"medicine_name": "Paracetamol 500mg", "quantity": 100},
    )
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/api/agents/supply-chain/search-suppliers",
        headers={"X-API-Key": "test-key"},
        json={"medicine_name": "Paracetamol 500mg", "quantity": 100},
    )
    assert authorized.status_code == 200


def test_supply_chain_routes_rate_limit(monkeypatch):
    app = FastAPI()
    app.include_router(supply_chain.router, prefix="/api")
    app.dependency_overrides[supply_chain.get_db] = _fake_get_db

    monkeypatch.delenv("AGENTS_API_KEY", raising=False)
    monkeypatch.setattr(supply_chain, "_RATE_LIMIT_REQUESTS", 1)
    monkeypatch.setattr(supply_chain, "_RATE_LIMIT_WINDOW_SEC", 60)
    supply_chain._RATE_LIMIT_BUCKETS.clear()

    monkeypatch.setattr(
        supply_chain,
        "_search_suppliers",
        lambda payload, db: {"ok": True, "result": {"suppliers": []}},
    )

    client = TestClient(app)

    first = client.post(
        "/api/agents/supply-chain/search-suppliers",
        json={"medicine_name": "Paracetamol 500mg", "quantity": 100},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/agents/supply-chain/search-suppliers",
        json={"medicine_name": "Paracetamol 500mg", "quantity": 100},
    )
    assert second.status_code == 429
