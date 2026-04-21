from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import anomaly_detector


def _build_synthetic_df() -> pd.DataFrame:
    np.random.seed(42)
    base_date = pd.Timestamp("2026-01-01")
    rows = []

    for day in range(60):
        for item_id in [1, 2]:
            qty = max(0, int(np.random.normal(20 if item_id == 1 else 12, 2)))
            rows.append(
                {
                    "item_id": item_id,
                    "department_id": 1,
                    "quantity_used": qty,
                    "usage_date": base_date + pd.Timedelta(days=day),
                }
            )

    rows.append(
        {
            "item_id": 1,
            "department_id": 1,
            "quantity_used": 300,
            "usage_date": base_date + pd.Timedelta(days=61),
        }
    )

    rows.append(
        {
            "item_id": 1,
            "department_id": 1,
            "quantity_used": 0,
            "usage_date": base_date + pd.Timedelta(days=62),
        }
    )

    rows.append(
        {
            "item_id": 2,
            "department_id": 3,
            "quantity_used": 90,
            "usage_date": base_date + pd.Timedelta(days=63),
        }
    )

    return pd.DataFrame(rows)


def test_train_and_detect_rules(tmp_path, monkeypatch):
    monkeypatch.setattr(anomaly_detector, "PKL_IFOREST", tmp_path / "iforest.pkl")
    monkeypatch.setattr(anomaly_detector, "PKL_META", tmp_path / "meta.pkl")

    df = _build_synthetic_df()
    meta = anomaly_detector.train(df)

    assert meta["contamination"] == 0.05
    assert anomaly_detector.is_trained() is True

    detected = anomaly_detector.detect(df)
    flagged = detected[detected["anomaly_flag"]]

    assert not flagged.empty
    reasons_flat = set(r for reasons in flagged["reasons"] for r in reasons)
    assert "sudden_10x_spike" in reasons_flat
    assert "zero_with_high_baseline" in reasons_flat


def test_predict_recent_response_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(anomaly_detector, "PKL_IFOREST", tmp_path / "iforest.pkl")
    monkeypatch.setattr(anomaly_detector, "PKL_META", tmp_path / "meta.pkl")

    df = _build_synthetic_df()
    anomaly_detector.train(df)
    out = anomaly_detector.predict_recent(df, days=14, limit=20)

    assert "total_anomalies" in out
    assert "anomalies" in out
    assert isinstance(out["anomalies"], list)
