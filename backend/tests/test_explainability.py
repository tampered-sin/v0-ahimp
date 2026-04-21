from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.explainability import LIMEExplainer, SHAPExplainer, build_item_explanation


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


class _StubRegressor:
    def predict(self, X):
        arr = np.asarray(X, dtype=float)
        return arr[:, 0] * 0.6 + arr[:, 1] * 0.4


def _build_feature_df() -> pd.DataFrame:
    rows = []
    start = pd.Timestamp("2026-01-01")
    rng = np.random.default_rng(42)
    for item_id in [1, 2]:
        for offset in range(40):
            rows.append(
                {
                    "item_id": item_id,
                    "item_name": f"Item {item_id}",
                    "usage_date": start + pd.Timedelta(days=offset),
                    "quantity_used": float(20 + rng.normal()),
                    "rolling_7d": float(18 + rng.normal()),
                    "rolling_30d": float(19 + rng.normal()),
                    "lag_7": float(17 + rng.normal()),
                    "lag_14": float(16 + rng.normal()),
                    "day_of_week": float((offset % 7)),
                    "month": float(1),
                    "velocity": float(rng.normal()),
                    "stock_ratio": float(2.0 + rng.normal() * 0.1),
                    "avg_lead_time_days": float(3.0),
                    "reliability_score": float(0.9),
                }
            )
    return pd.DataFrame(rows)


def test_build_item_explanation_success():
    feat_df = _build_feature_df()
    model = _StubRegressor()
    shap_explainer = SHAPExplainer()
    lime_explainer = LIMEExplainer()

    payload = build_item_explanation(
        model=model,
        feat_df=feat_df,
        item_id=1,
        feature_names=FEATURE_NAMES,
        shap_explainer=shap_explainer,
        lime_explainer=lime_explainer,
        top_k=6,
    )

    assert payload["item_id"] == 1
    assert payload["item_name"] == "Item 1"
    assert "shap" in payload
    assert "lime" in payload
    assert isinstance(payload["feature_snapshot"], list)
    assert payload["shap"]["global"]["available"] in (True, False)
    assert payload["shap"]["local"]["available"] in (True, False)
    assert payload["lime"]["available"] in (True, False)


def test_build_item_explanation_missing_item():
    feat_df = _build_feature_df()
    payload = build_item_explanation(
        model=_StubRegressor(),
        feat_df=feat_df,
        item_id=999,
        feature_names=FEATURE_NAMES,
        shap_explainer=SHAPExplainer(),
        lime_explainer=LIMEExplainer(),
    )

    assert payload == {"error": "No data for this item"}
