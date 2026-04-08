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
