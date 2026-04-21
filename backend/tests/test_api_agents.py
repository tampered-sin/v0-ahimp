from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from api import agents


def _fake_get_db():
    class _DB:
        pass

    yield _DB()


def test_agents_data_ingestion_sync(monkeypatch):
    app = FastAPI()
    app.include_router(agents.router, prefix="/api")
    app.dependency_overrides[agents.get_db] = _fake_get_db

    monkeypatch.setattr(
        agents,
        "run_data_ingestion_task",
        lambda payload, db: {
            "ok": True,
            "agent": "data-ingestion-agent",
            "task": "data_ingestion",
            "result": {"inserted": 2},
        },
    )

    client = TestClient(app)
    resp = client.post(
        "/api/agents/data-ingestion",
        json={
            "source_type": "records",
            "run_async": False,
            "records": [
                {
                    "item_id": 1,
                    "department_id": 1,
                    "quantity_used": 10,
                    "usage_date": "2026-01-01",
                }
            ],
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["result"]["result"]["inserted"] == 2


def test_agents_data_ingestion_async_and_status():
    app = FastAPI()
    app.include_router(agents.router, prefix="/api")
    app.dependency_overrides[agents.get_db] = _fake_get_db

    client = TestClient(app)
    resp = client.post(
        "/api/agents/data-ingestion",
        json={
            "source_type": "records",
            "run_async": True,
            "records": [
                {
                    "item_id": 1,
                    "department_id": 1,
                    "quantity_used": 10,
                    "usage_date": "2026-01-01",
                }
            ],
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert "job_id" in body

    status_resp = client.get(f"/api/agents/data-ingestion/status/{body['job_id']}")
    assert status_resp.status_code == 200


def test_admin_ingestion_audit_list(monkeypatch):
    app = FastAPI()
    app.include_router(agents.router, prefix="/api")
    app.dependency_overrides[agents.get_db] = _fake_get_db

    monkeypatch.setattr(
        agents,
        "list_audit_records",
        lambda db, status=None, limit=100, offset=0: [
            {
                "audit_id": 11,
                "status": status or "PENDING",
                "severity": "RED",
            }
        ],
    )

    client = TestClient(app)
    resp = client.get("/api/admin/ingestion-audit?status=PENDING&limit=20&offset=0")

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["records"][0]["audit_id"] == 11


def test_admin_ingestion_audit_review(monkeypatch):
    app = FastAPI()
    app.include_router(agents.router, prefix="/api")
    app.dependency_overrides[agents.get_db] = _fake_get_db

    monkeypatch.setattr(
        agents,
        "review_audit_record",
        lambda db, audit_id, action, reviewed_by, comment=None, create_consumption_record=False: {
            "audit_id": audit_id,
            "status": "APPROVED",
            "reviewed_by": reviewed_by,
            "reviewed_at": "2026-01-01T00:00:00+00:00",
        },
    )

    client = TestClient(app)
    resp = client.post(
        "/api/admin/ingestion-audit/22/review",
        json={
            "action": "approve",
            "reviewed_by": "pharmacist-1",
            "comment": "looks valid",
            "create_consumption_record": True,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["audit_id"] == 22
    assert body["status"] == "APPROVED"


def test_admin_ingestion_audit_review_not_found(monkeypatch):
    app = FastAPI()
    app.include_router(agents.router, prefix="/api")
    app.dependency_overrides[agents.get_db] = _fake_get_db

    def _raise_not_found(*args, **kwargs):
        raise ValueError("Audit record not found")

    monkeypatch.setattr(agents, "review_audit_record", _raise_not_found)

    client = TestClient(app)
    resp = client.post(
        "/api/admin/ingestion-audit/999/review",
        json={
            "action": "approve",
            "reviewed_by": "pharmacist-1",
            "create_consumption_record": False,
        },
    )

    assert resp.status_code == 404


def test_agents_supply_chain_at_risk_and_optimize(monkeypatch):
    app = FastAPI()
    app.include_router(agents.router, prefix="/api")
    app.dependency_overrides[agents.get_db] = _fake_get_db

    monkeypatch.setattr(
        agents,
        "run_supply_chain_task",
        lambda payload, db, auto_purchase: {
            "ok": True,
            "agent": "supply-chain-agent",
            "result": {
                "auto_purchase": auto_purchase,
                "decisions": [],
            },
        },
    )

    client = TestClient(app)

    at_risk_resp = client.get("/api/agents/supply-chain/at-risk")
    assert at_risk_resp.status_code == 200
    assert at_risk_resp.json()["result"]["auto_purchase"] is False

    optimize_resp = client.post(
        "/api/agents/supply-chain/optimize",
        json={
            "risk_threshold": 0.7,
            "max_items": 5,
            "cadence_hours": 1,
            "supplier_overrides": {},
        },
    )
    assert optimize_resp.status_code == 200
    assert optimize_resp.json()["result"]["auto_purchase"] is True


def test_agents_logs_and_dashboard(monkeypatch):
    app = FastAPI()
    app.include_router(agents.router, prefix="/api")
    app.dependency_overrides[agents.get_db] = _fake_get_db

    agents._JOBS.clear()

    monkeypatch.setattr(
        agents,
        "run_data_ingestion_task",
        lambda payload, db: {
            "ok": True,
            "agent": "data-ingestion-agent",
            "task": "data_ingestion",
            "result": {"inserted": 1},
        },
    )
    monkeypatch.setattr(
        agents,
        "list_audit_records",
        lambda db, status=None, limit=1000, offset=0: [{"audit_id": 1, "status": "PENDING"}],
    )
    monkeypatch.setattr(
        agents,
        "list_agent_logs",
        lambda db, agent_name=None, status=None, level=None, search=None, limit=100, offset=0: {
            "count": 1,
            "records": [
                {
                    "log_id": 1,
                    "agent_name": "data-ingestion-agent",
                    "task_description": "data_ingestion",
                    "status": "succeeded",
                    "level": "INFO",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "completed_at": "2026-01-01T00:00:01+00:00",
                    "result": {"result": {"inserted": 1}},
                    "errors": None,
                }
            ],
        },
    )
    monkeypatch.setattr(
        agents,
        "summarize_agent_logs",
        lambda db, preview_limit=20: {
            "counts": {"succeeded": 1},
            "preview": [
                {
                    "log_id": 1,
                    "agent_name": "data-ingestion-agent",
                    "task_description": "data_ingestion",
                    "status": "succeeded",
                    "level": "INFO",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "completed_at": "2026-01-01T00:00:01+00:00",
                    "result": {"result": {"inserted": 1}},
                    "errors": None,
                }
            ],
        },
    )

    client = TestClient(app)
    ingest = client.post(
        "/api/agents/data-ingestion",
        json={
            "source_type": "records",
            "run_async": False,
            "records": [
                {
                    "item_id": 1,
                    "department_id": 1,
                    "quantity_used": 10,
                    "usage_date": "2026-01-01",
                }
            ],
        },
    )
    assert ingest.status_code == 200

    logs_resp = client.get("/api/agents/logs")
    assert logs_resp.status_code == 200
    assert logs_resp.json()["count"] >= 1

    dashboard_resp = client.get("/api/agents/dashboard")
    assert dashboard_resp.status_code == 200
    payload = dashboard_resp.json()
    assert payload["audit"]["pending_count"] == 1
    assert "jobs" in payload
    assert payload["log_counts"]["succeeded"] == 1


def test_agents_api_key_auth(monkeypatch):
    app = FastAPI()
    app.include_router(agents.router, prefix="/api")
    app.dependency_overrides[agents.get_db] = _fake_get_db

    monkeypatch.setenv("AGENTS_API_KEY", "test-key")
    monkeypatch.setattr(
        agents,
        "run_data_ingestion_task",
        lambda payload, db: {"ok": True, "result": {"inserted": 1}},
    )
    monkeypatch.setattr(
        agents,
        "list_agent_logs",
        lambda db, agent_name=None, status=None, level=None, search=None, limit=100, offset=0: {
            "count": 0,
            "records": [],
        },
    )

    client = TestClient(app)

    unauthorized = client.get("/api/agents/logs")
    assert unauthorized.status_code == 401

    authorized = client.get("/api/agents/logs", headers={"X-API-Key": "test-key"})
    assert authorized.status_code == 200


def test_agents_rate_limit(monkeypatch):
    app = FastAPI()
    app.include_router(agents.router, prefix="/api")
    app.dependency_overrides[agents.get_db] = _fake_get_db

    monkeypatch.delenv("AGENTS_API_KEY", raising=False)
    monkeypatch.setattr(agents, "_RATE_LIMIT_REQUESTS", 1)
    monkeypatch.setattr(agents, "_RATE_LIMIT_WINDOW_SEC", 60)
    agents._RATE_LIMIT_BUCKETS.clear()
    monkeypatch.setattr(
        agents,
        "list_agent_logs",
        lambda db, agent_name=None, status=None, level=None, search=None, limit=100, offset=0: {
            "count": 0,
            "records": [],
        },
    )

    client = TestClient(app)

    first = client.get("/api/agents/logs")
    assert first.status_code == 200

    second = client.get("/api/agents/logs")
    assert second.status_code == 429
