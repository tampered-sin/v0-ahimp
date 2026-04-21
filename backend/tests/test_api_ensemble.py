from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from api import ensemble


def _fake_get_db():
    class _DB:
        pass

    yield _DB()


def test_ensemble_forecast_uses_available_models(monkeypatch):
    app = FastAPI()
    app.include_router(ensemble.router, prefix="/api")
    app.dependency_overrides[ensemble.get_db] = _fake_get_db

    monkeypatch.setattr(ensemble.demand_model, "is_trained", lambda: True)
    monkeypatch.setattr(
        ensemble,
        "load_consumption_df",
        lambda db: pd.DataFrame(
            {
                "item_id": [1, 1],
                "item_name": ["Item A", "Item A"],
                "usage_date": ["2026-01-01", "2026-01-02"],
                "quantity_used": [10, 12],
                "reorder_point": [5, 5],
                "avg_lead_time_days": [3, 3],
                "reliability_score": [0.9, 0.9],
            }
        ),
    )
    monkeypatch.setattr(
        ensemble,
        "build_demand_features",
        lambda df: pd.DataFrame(
            {
                "item_id": [1],
                "usage_date": ["2026-01-02"],
                "quantity_used": [12],
                "reorder_point": [5],
                "avg_lead_time_days": [3],
                "reliability_score": [0.9],
                "rolling_7d": [11],
                "rolling_30d": [11],
                "lag_7": [10],
                "lag_14": [9],
                "day_of_week": [2],
                "month": [1],
                "velocity": [1.0],
                "stock_ratio": [2.0],
            }
        ),
    )

    # lgbm-like forecast
    monkeypatch.setattr(
        ensemble.demand_model,
        "predict_forecast",
        lambda feat_df, item_id: {
            "forecast": [
                {"predicted": 20.0},
                {"predicted": 21.0},
            ]
        },
    )
    # lr forecast
    monkeypatch.setattr(
        ensemble.demand_model,
        "predict_forecast_lr",
        lambda feat_df, item_id: {
            "forecast": [
                {"predicted": 10.0},
                {"predicted": 11.0},
            ]
        },
    )

    client = TestClient(app)
    resp = client.get("/api/ensemble-forecast", params={"item_id": 1})

    assert resp.status_code == 200
    data = resp.json()
    assert "forecast" in data
    assert len(data["forecast"]) == 2
    assert "models_used" in data
    assert "lgbm" in data["models_used"] or "xgb" in data["models_used"]
