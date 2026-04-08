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
