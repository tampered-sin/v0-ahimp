from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from api import alerts


def test_recent_alerts_endpoint(monkeypatch):
    app = FastAPI()
    app.include_router(alerts.router, prefix="/api")

    monkeypatch.setattr(
        alerts,
        "get_recent_alerts",
        lambda limit, severity: [
            {
                "alert_id": 1,
                "severity": "RED",
                "channels": ["log"],
                "subject": "test",
            }
        ],
    )

    client = TestClient(app)
    resp = client.get("/api/alerts/recent", params={"limit": 10, "severity": "RED"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["alerts"][0]["severity"] == "RED"
