from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from api import consumption


class _FakeDB:
    def __init__(self) -> None:
        self.rows = []

    def add_all(self, rows):
        self.rows.extend(rows)

    def commit(self):
        return None

    def rollback(self):
        return None


def _fake_get_db():
    yield _FakeDB()


def test_ingest_returns_alerts_and_notification(monkeypatch):
    app = FastAPI()
    app.include_router(consumption.router, prefix="/api")
    app.dependency_overrides[consumption.get_db] = _fake_get_db

    # Stub anomaly pipeline + notifier behavior
    monkeypatch.setattr(consumption.anomaly_detector, "is_trained", lambda: True)
    monkeypatch.setattr(
        consumption,
        "load_consumption_df",
        lambda db: pd.DataFrame(
            {
                "item_id": [1],
                "department_id": [1],
                "quantity_used": [50],
                "usage_date": ["2026-01-01"],
            }
        ),
    )
    monkeypatch.setattr(
        consumption.anomaly_detector,
        "predict_recent",
        lambda df, days, limit: {
            "red_alerts": 2,
            "yellow_alerts": 1,
            "anomalies": [
                {
                    "item_id": 1,
                    "department_id": 1,
                    "usage_date": "2026-01-01",
                    "quantity_used": 500,
                    "severity": "RED",
                    "anomaly_score": 0.9,
                    "reasons": ["sudden_10x_spike"],
                }
            ],
        },
    )
    monkeypatch.setattr(
        consumption,
        "send_anomaly_alert",
        lambda subject, body, severity="RED": {"sent": True, "channels": ["log"]},
    )

    client = TestClient(app)
    payload = {
        "records": [
            {
                "item_id": 1,
                "department_id": 1,
                "quantity_used": 10,
                "usage_date": "2026-01-02",
                "patient_type": "general",
            }
        ],
        "run_anomaly_detection": True,
    }
    resp = client.post("/api/consumption/ingest", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["inserted"] == 1
    assert data["alerts"]["red"] == 2
    assert data["notification"]["sent"] is True


def test_ingest_without_anomaly_scan(monkeypatch):
    app = FastAPI()
    app.include_router(consumption.router, prefix="/api")
    app.dependency_overrides[consumption.get_db] = _fake_get_db

    client = TestClient(app)
    payload = {
        "records": [
            {
                "item_id": 2,
                "department_id": 3,
                "quantity_used": 8,
                "usage_date": "2026-01-03",
            }
        ],
        "run_anomaly_detection": False,
    }
    resp = client.post("/api/consumption/ingest", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["anomaly_detection_run"] is False
