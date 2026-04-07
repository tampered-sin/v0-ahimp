from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.sequence_generator import create_demand_sequences, temporal_train_test_split


def _sample_features(rows: int = 40, item_id: int = 1) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=rows, freq="D")
    return pd.DataFrame(
        {
            "item_id": [item_id] * rows,
            "usage_date": dates,
            "rolling_7d": np.random.rand(rows) * 10,
            "rolling_30d": np.random.rand(rows) * 12,
            "lag_7": np.random.rand(rows) * 8,
            "lag_14": np.random.rand(rows) * 7,
            "day_of_week": [d.dayofweek for d in dates],
            "month": [d.month for d in dates],
            "velocity": np.random.randn(rows),
            "stock_ratio": np.random.rand(rows),
            "avg_lead_time_days": np.random.rand(rows) * 5 + 1,
            "reliability_score": np.random.rand(rows) * 0.5 + 0.5,
            "quantity_used": np.random.rand(rows) * 20 + 5,
        }
    )


def test_create_demand_sequences_shape():
    df = pd.concat([_sample_features(item_id=1), _sample_features(item_id=2)], ignore_index=True)
    X, y = create_demand_sequences(df, lookback=14, horizon=14)

    assert X.ndim == 3
    assert y.ndim == 2
    assert X.shape[1] == 14
    assert X.shape[2] == 10
    assert y.shape[1] == 14
    assert len(X) == len(y)


def test_temporal_split_keeps_order_and_sizes():
    df = _sample_features(rows=60)
    X, y = create_demand_sequences(df, lookback=14, horizon=14)
    X_train, X_test, y_train, y_test = temporal_train_test_split(X, y, train_ratio=0.8)

    assert len(X_train) > len(X_test)
    assert len(X_train) + len(X_test) == len(X)
    assert len(y_train) + len(y_test) == len(y)
