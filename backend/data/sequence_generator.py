"""Utilities to build time-series sequences for recurrent demand models."""
from __future__ import annotations

import numpy as np
import pandas as pd

from models.demand_model import FEATURE_COLS


def generate_sequences(
    feat_df: pd.DataFrame,
    lookback: int = 14,
    horizon: int = 14,
    feature_cols: list[str] | None = None,
    target_col: str = "quantity_used",
) -> tuple[np.ndarray, np.ndarray]:
    """
    Build per-item rolling windows for sequence-to-vector forecasting.

    Returns:
        X with shape (n_samples, lookback, n_features)
        y with shape (n_samples, horizon)
    """
    if lookback <= 0 or horizon <= 0:
        raise ValueError("lookback and horizon must be positive")

    cols = feature_cols or FEATURE_COLS
    required = ["item_id", "usage_date", target_col, *cols]
    missing = [col for col in required if col not in feat_df.columns]
    if missing:
        raise ValueError(f"Missing required columns for sequence generation: {missing}")

    X_windows: list[np.ndarray] = []
    y_windows: list[np.ndarray] = []

    for _, group in feat_df.groupby("item_id"):
        grp = group.sort_values("usage_date").reset_index(drop=True)
        if len(grp) < lookback + horizon:
            continue

        feat_values = grp[cols].astype(float).to_numpy()
        target_values = grp[target_col].astype(float).to_numpy()
        max_start = len(grp) - lookback - horizon + 1

        for start in range(max_start):
            x_slice = feat_values[start : start + lookback]
            y_slice = target_values[start + lookback : start + lookback + horizon]
            X_windows.append(x_slice)
            y_windows.append(y_slice)

    if not X_windows:
        return np.empty((0, lookback, len(cols))), np.empty((0, horizon))

    return np.asarray(X_windows, dtype=np.float32), np.asarray(y_windows, dtype=np.float32)


def split_sequences(
    X: np.ndarray,
    y: np.ndarray,
    train_ratio: float = 0.8,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Chronologically split sequence arrays into train/test partitions."""
    if len(X) != len(y):
        raise ValueError("X and y must have identical sample counts")
    if len(X) == 0:
        raise ValueError("No sequences available for split")
    if not 0.0 < train_ratio < 1.0:
        raise ValueError("train_ratio must be between 0 and 1")

    split_idx = max(1, int(len(X) * train_ratio))
    split_idx = min(split_idx, len(X) - 1)
    return X[:split_idx], X[split_idx:], y[:split_idx], y[split_idx:]
