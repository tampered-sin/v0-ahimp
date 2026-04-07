"""
Sequence generation utilities for LSTM/GRU demand forecasting.

Creates supervised learning windows:
- Input: 14-day lookback with 10 engineered features
- Target: next 14-day demand quantities
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_COLS = [
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
TARGET_COL = "quantity_used"


def create_sequences_for_item(
    item_df: pd.DataFrame,
    lookback: int,
    horizon: int,
    feature_cols: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Create rolling sequences for a single item time series."""
    cols = feature_cols or FEATURE_COLS
    required = cols + [TARGET_COL]
    missing = [c for c in required if c not in item_df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    series = item_df.sort_values("usage_date").reset_index(drop=True)
    X_raw = series[cols].astype(float).to_numpy()
    y_raw = series[TARGET_COL].astype(float).to_numpy()

    total = len(series) - lookback - horizon + 1
    if total <= 0:
        return np.empty((0, lookback, len(cols))), np.empty((0, horizon))

    X_seq = []
    y_seq = []
    for i in range(total):
        X_seq.append(X_raw[i : i + lookback])
        y_seq.append(y_raw[i + lookback : i + lookback + horizon])

    return np.array(X_seq, dtype=np.float32), np.array(y_seq, dtype=np.float32)


def create_demand_sequences(
    feat_df: pd.DataFrame,
    lookback: int = 14,
    horizon: int = 14,
    feature_cols: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Build multi-item LSTM/GRU dataset from engineered demand features.

    Returns:
        X: shape (samples, lookback, n_features)
        y: shape (samples, horizon)
    """
    cols = feature_cols or FEATURE_COLS
    if "item_id" not in feat_df.columns:
        raise ValueError("feat_df must contain 'item_id' column")

    X_parts = []
    y_parts = []

    for _, item_df in feat_df.groupby("item_id"):
        X_item, y_item = create_sequences_for_item(
            item_df=item_df,
            lookback=lookback,
            horizon=horizon,
            feature_cols=cols,
        )
        if len(X_item) > 0:
            X_parts.append(X_item)
            y_parts.append(y_item)

    if not X_parts:
        return np.empty((0, lookback, len(cols))), np.empty((0, horizon))

    return np.concatenate(X_parts, axis=0), np.concatenate(y_parts, axis=0)


def temporal_train_test_split(
    X: np.ndarray,
    y: np.ndarray,
    train_ratio: float = 0.8,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Split sequence dataset without shuffling to preserve chronology."""
    if len(X) != len(y):
        raise ValueError("X and y must have the same number of samples")
    if len(X) == 0:
        raise ValueError("Cannot split empty dataset")

    split_idx = int(len(X) * train_ratio)
    split_idx = max(1, min(split_idx, len(X) - 1))

    return X[:split_idx], X[split_idx:], y[:split_idx], y[split_idx:]
