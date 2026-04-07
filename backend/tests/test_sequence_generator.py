from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.sequence_generator import generate_sequences, split_sequences


def _sample_df() -> pd.DataFrame:
    rows = []
    for day in range(50):
        rows.append(
            {
                "item_id": 1,
                "usage_date": f"2026-01-{(day % 28) + 1:02d}",
                "quantity_used": 10 + day,
                "rolling_7d": 10 + day,
                "rolling_30d": 10 + day,
                "lag_7": max(0, day - 7),
                "lag_14": max(0, day - 14),
                "day_of_week": day % 7,
                "month": 1,
                "velocity": 1.0,
                "stock_ratio": 1.2,
                "avg_lead_time_days": 3,
                "reliability_score": 0.9,
            }
        )
    df = pd.DataFrame(rows)
    df["usage_date"] = pd.to_datetime(df["usage_date"])
    return df


def test_generate_sequences_shapes():
    df = _sample_df()
    X, y = generate_sequences(df, lookback=14, horizon=14)

    assert X.ndim == 3
    assert y.ndim == 2
    assert X.shape[1] == 14
    assert y.shape[1] == 14
    assert len(X) == len(y)


def test_split_sequences_chronological_partitions():
    df = _sample_df()
    X, y = generate_sequences(df, lookback=14, horizon=7)
    X_train, X_test, y_train, y_test = split_sequences(X, y, train_ratio=0.8)

    assert len(X_train) > 0
    assert len(X_test) > 0
    assert len(X_train) + len(X_test) == len(X)
    assert len(y_train) + len(y_test) == len(y)
