from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from api import explain


FEATURE_NAMES = [
    "rolling_7d",
    "rolling_30d",
    "lag_7",
    "lag_14",
    "day_of_week",
    "month",
    "velocity",
    "stock_ratio",
    "avg_lead_time_days",
    "reliability_score",
]


class _StubModel:
    def predict(self, X):
        arr = pd.DataFrame(X)
        return (arr.iloc[:, 0] * 0.5 + arr.iloc[:, 1] * 0.5).to_numpy()


def _fake_get_db():
    class _DB:
        pass

    yield _DB()


def _raw_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "consumption_id": [1001, 1002],
            "item_id": [1, 1],
            "item_name": ["Gloves", "Gloves"],
            "usage_date": ["2026-01-10", "2026-01-11"],
            "quantity_used": [50, 55],
        }
    )


def _feat_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "item_id": [1, 1],
            "item_name": ["Gloves", "Gloves"],
            "usage_date": ["2026-01-10", "2026-01-11"],
            "quantity_used": [50, 55],
            "rolling_7d": [48.0, 50.0],
            "rolling_30d": [45.0, 46.0],
            "lag_7": [43.0, 44.0],
            "lag_14": [40.0, 41.0],
            "day_of_week": [4.0, 5.0],
            "month": [1.0, 1.0],
            "velocity": [1.2, 1.3],
            "stock_ratio": [2.2, 2.3],
            "avg_lead_time_days": [3.0, 3.0],
            "reliability_score": [0.9, 0.9],
        }
    )


def test_explain_item_route(monkeypatch):
    app = FastAPI()
    app.include_router(explain.router, prefix="/api")
    app.dependency_overrides[explain.get_db] = _fake_get_db

    monkeypatch.setattr(explain.demand_model, "is_trained", lambda: True)
    monkeypatch.setattr(explain, "load_consumption_df", lambda db: _raw_df())
    monkeypatch.setattr(explain, "build_demand_features", lambda df: _feat_df())
    monkeypatch.setattr(explain.demand_model, "_load_lgbm", lambda: _StubModel())
    monkeypatch.setattr(explain.demand_model, "_load_meta", lambda: {"feature_cols": FEATURE_NAMES})
    monkeypatch.setattr(
        explain,
        "build_item_explanation",
        lambda **kwargs: {
            "item_id": kwargs["item_id"],
            "item_name": "Gloves",
            "usage_date": "2026-01-11",
            "feature_snapshot": [],
            "shap": {"global": {"available": True}, "local": {"available": True}, "force_plot": {}},
            "lime": {"available": True},
        },
    )
    monkeypatch.setattr(
        explain.demand_model,
        "predict_forecast",
        lambda feat_df, item_id: {"forecast": [{"date": "2026-01-12", "predicted": 56.0}]},
    )

    client = TestClient(app)
    resp = client.get("/api/explain/item/1")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["item_id"] == 1
    assert payload["model"] == "LightGBM"
    assert "forecast_preview" in payload


def test_explain_prediction_route(monkeypatch):
    app = FastAPI()
    app.include_router(explain.router, prefix="/api")
    app.dependency_overrides[explain.get_db] = _fake_get_db

    monkeypatch.setattr(explain.demand_model, "is_trained", lambda: True)
    monkeypatch.setattr(explain, "load_consumption_df", lambda db: _raw_df())
    monkeypatch.setattr(explain, "build_demand_features", lambda df: _feat_df())
    monkeypatch.setattr(explain.demand_model, "_load_lgbm", lambda: _StubModel())
    monkeypatch.setattr(explain.demand_model, "_load_meta", lambda: {"feature_cols": FEATURE_NAMES})
    monkeypatch.setattr(
        explain,
        "build_item_explanation",
        lambda **kwargs: {
            "item_id": kwargs["item_id"],
            "item_name": "Gloves",
            "usage_date": "2026-01-11",
            "feature_snapshot": [],
            "shap": {"global": {"available": True}, "local": {"available": True}, "force_plot": {}},
            "lime": {"available": True},
        },
    )

    client = TestClient(app)
    resp = client.get("/api/explain/prediction/1001")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["prediction_id"] == 1001
    assert payload["item_id"] == 1


def test_explain_prediction_not_found(monkeypatch):
    app = FastAPI()
    app.include_router(explain.router, prefix="/api")
    app.dependency_overrides[explain.get_db] = _fake_get_db

    monkeypatch.setattr(explain.demand_model, "is_trained", lambda: True)
    monkeypatch.setattr(explain, "load_consumption_df", lambda db: _raw_df())
    monkeypatch.setattr(explain, "build_demand_features", lambda df: _feat_df())

    client = TestClient(app)
    resp = client.get("/api/explain/prediction/9999")

    assert resp.status_code == 404
