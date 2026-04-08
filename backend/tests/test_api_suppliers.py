from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from api import suppliers


def _fake_get_db():
    class _DB:
        pass

    yield _DB()


def test_supplier_scoring_route_success(monkeypatch):
    app = FastAPI()
    app.include_router(suppliers.router, prefix="/api")
    app.dependency_overrides[suppliers.get_db] = _fake_get_db

    monkeypatch.setattr(
        suppliers,
        "score_suppliers",
        lambda db, item_id, supplier_overrides=None: {
            "item_id": item_id,
            "suppliers": [{"supplier_id": 1, "supplier_name": "Alpha", "score": 88.1, "rank": 1}],
        },
    )

    client = TestClient(app)
    resp = client.post(
        "/api/suppliers/scoring",
        json={
            "item_id": 1,
            "supplier_overrides": [
                {
                    "supplier_id": 1,
                    "distance_km": 100,
                    "sentiment_score": 0.5,
                    "review_text": "excellent communication",
                }
            ],
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["item_id"] == 1
    assert body["suppliers"][0]["rank"] == 1


def test_supplier_scoring_route_missing_item(monkeypatch):
    app = FastAPI()
    app.include_router(suppliers.router, prefix="/api")
    app.dependency_overrides[suppliers.get_db] = _fake_get_db

    def _raise(*args, **kwargs):
        raise ValueError("Item not found")

    monkeypatch.setattr(suppliers, "score_suppliers", _raise)

    client = TestClient(app)
    resp = client.post("/api/suppliers/scoring", json={"item_id": 999})

    assert resp.status_code == 404
