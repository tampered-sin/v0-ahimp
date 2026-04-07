"""
CatBoost Integration for Demand Forecasting Model

Combines LightGBM (fast universal model) with CatBoost (optimal for categorical features)
for improved performance and interpretability on categorical supplier/department/item_type data.
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from config import PKL_DIR, RANDOM_SEED, FORECAST_HORIZON
from models.catboost_model import (
    build_model as build_catboost_model,
    cross_validate_r2 as catboost_cv_r2,
    load_model as load_catboost_model,
    save_model as save_catboost_model,
    get_feature_importance,
    prepare_catboost_array,
)
try:
    from models.lightgbm_model import (
        build_model as build_lgbm_model,
        cross_validate_r2 as lgbm_cv_r2,
        load_model as load_lgbm_model,
    )
except ModuleNotFoundError:
    build_lgbm_model = None
    lgbm_cv_r2 = None
    load_lgbm_model = None

FEATURE_COLS = [
    "rolling_7d", "rolling_30d", "lag_7", "lag_14",
    "day_of_week", "month", "velocity", "stock_ratio",
    "avg_lead_time_days", "reliability_score",
]

# Categorical columns that exist in preprocessed data (indices)
CATEGORICAL_FEATURE_INDICES = []  # Will be set dynamically based on feature matrix

# Feature names for categorical features (to identify in results)
CATEGORICAL_FEATURE_NAMES = [
    "supplier_id", "department_id", "category", "patient_type"
]

PKL_CATBOOST = PKL_DIR / "demand_catboost.pkl"
PKL_CATBOOST_META = PKL_DIR / "demand_catboost_meta.pkl"


def build_demand_features_with_categorical(feat_df: pd.DataFrame) -> tuple:
    """
    Engineer features from raw consumption data, preserving categorical columns.

    Args:
        feat_df: DataFrame with aggregated consumption records

    Returns:
        Tuple of (feature_matrix, target_vector, categorical_feature_indices, feature_names)
    """
    # Ensure we have required columns
    required_cols = FEATURE_COLS + ["quantity_used"]
    for col in required_cols:
        if col not in feat_df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Use any configured categorical columns that are actually present
    present_categorical_cols = [
        col for col in CATEGORICAL_FEATURE_NAMES if col in feat_df.columns
    ]
    has_categorical = len(present_categorical_cols) > 0

    if has_categorical:
        # Include only categorical features available in the engineered dataset
        all_feature_cols = FEATURE_COLS + present_categorical_cols
        feature_matrix = feat_df[all_feature_cols].values

        # Identify categorical feature indices (they come at the end)
        cat_indices = list(range(len(FEATURE_COLS), len(all_feature_cols)))

        feature_names = all_feature_cols
    else:
        # Fall back to numeric features only
        feature_matrix = feat_df[FEATURE_COLS].values
        cat_indices = []
        feature_names = FEATURE_COLS

    target_vector = feat_df["quantity_used"].values

    return feature_matrix, target_vector, cat_indices, feature_names


def train_catboost(feat_df: pd.DataFrame) -> dict:
    """
    Train CatBoost model with categorical feature support.

    Args:
        feat_df: Feature DataFrame from demand model

    Returns:
        Dictionary with model metrics and metadata
    """
    feat_df = feat_df.dropna(subset=FEATURE_COLS + ["quantity_used"])

    # Build features with categorical support
    X, y, cat_indices, feature_names = build_demand_features_with_categorical(feat_df)

    # Handle categorical features by encoding (prepare_catboost_array handles dtype conversion)
    cat_encoding: dict = {}
    if cat_indices:
        for idx in cat_indices:
            col_name = feature_names[idx]
            unique_vals = np.unique(X[:, idx])
            val_to_idx = {val: i for i, val in enumerate(unique_vals)}
            cat_encoding[col_name] = val_to_idx
            X[:, idx] = [val_to_idx[val] for val in X[:, idx]]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, shuffle=False
    )

    # Prepare arrays with correct types for CatBoost categorical handling
    X_train = prepare_catboost_array(X_train, cat_indices)
    X_test = prepare_catboost_array(X_test, cat_indices)

    # --- CatBoost Training ---
    catboost = build_catboost_model(RANDOM_SEED)
    catboost.fit(
        X_train,
        y_train,
        cat_features=cat_indices,
        verbose=False,
    )
    y_pred_catboost = catboost.predict(X_test)

    mae_catboost = float(mean_absolute_error(y_test, y_pred_catboost))
    rmse_catboost = float(np.sqrt(mean_squared_error(y_test, y_pred_catboost)))
    r2_catboost = float(r2_score(y_test, y_pred_catboost))

    # Cross-validation
    cv_r2_scores = catboost_cv_r2(X_train, y_train, cat_indices, RANDOM_SEED, folds=5)

    # Save model
    save_catboost_model(catboost, PKL_CATBOOST)

    # Feature importance with categorical insights
    importance = get_feature_importance(catboost, feature_names, CATEGORICAL_FEATURE_NAMES)

    # Compare with LightGBM baseline
    r2_lgbm = None
    if build_lgbm_model is not None:
        lgbm = build_lgbm_model(RANDOM_SEED)
        lgbm.fit(X_train, y_train)
        y_pred_lgbm = lgbm.predict(X_test)
        r2_lgbm = float(r2_score(y_test, y_pred_lgbm))

    meta = {
        "catboost": {
            "mae": mae_catboost,
            "rmse": rmse_catboost,
            "r2": r2_catboost,
            "cv_r2_scores": cv_r2_scores,
            "cv_r2_mean": float(np.mean(cv_r2_scores)) if cv_r2_scores else None,
            "categorical_features": list(feature_names[len(FEATURE_COLS):]) if cat_indices else [],
            "cat_feature_count": len(cat_indices),
        },
        "lgbm_baseline": {
            "r2": r2_lgbm,
        },
        "improvement": {
            "r2_delta": (r2_catboost - r2_lgbm) if r2_lgbm is not None else None,
            "mae_vs_baseline": mae_catboost,
        },
        "feature_importance": importance,
        "feature_cols": FEATURE_COLS,
        "categorical_cols": list(feature_names[len(FEATURE_COLS):]) if cat_indices else [],
        "cat_encoding": cat_encoding,
    }

    with open(PKL_CATBOOST_META, "wb") as f:
        pickle.dump(meta, f)

    lgbm_r2_str = f"{r2_lgbm:.3f}" if r2_lgbm is not None else "N/A"
    print(f"[CatBoost] MAE={mae_catboost:.2f}  RMSE={rmse_catboost:.2f}  R²={r2_catboost:.3f}  (vs LightGBM R²={lgbm_r2_str})")
    return meta


def is_trained() -> bool:
    """Check if CatBoost model has been trained and saved."""
    return PKL_CATBOOST.exists() and PKL_CATBOOST_META.exists()


def predict_forecast_catboost(feat_df: pd.DataFrame, item_id: int) -> dict:
    """
    Generate a 14-day demand forecast using CatBoost with categorical features.

    Args:
        feat_df: Feature DataFrame (must include categorical columns if available)
        item_id: Item ID to forecast

    Returns:
        Dictionary with forecast dates and predictions
    """
    if not is_trained():
        return {"error": "CatBoost model not trained"}

    catboost = load_catboost_model(PKL_CATBOOST)
    with open(PKL_CATBOOST_META, "rb") as f:
        meta = pickle.load(f)

    item_df = (
        feat_df[feat_df["item_id"] == item_id]
        .sort_values("usage_date")
        .tail(60)
        .reset_index(drop=True)
    )

    if item_df.empty:
        return {"error": "No data for this item"}

    # Seed forecast from last known state
    history = list(item_df["quantity_used"].values)
    forecast = []
    today = pd.Timestamp.today().normalize()

    # Determine which categorical columns were used at training time
    trained_cat_cols: list[str] = meta.get("categorical_cols", [])
    cat_encoding: dict = meta.get("cat_encoding", {})

    # Build static categorical feature values for this item (constant across forecast horizon)
    cat_values: list = []
    for col in trained_cat_cols:
        raw_val = item_df[col].iloc[0] if col in item_df.columns else None
        encoding = cat_encoding.get(col, {})
        # Map to the integer used during training; use len(encoding) as 'unknown' sentinel
        # to avoid colliding with any valid training value index
        cat_values.append(encoding.get(raw_val, len(encoding)))

    for day in range(FORECAST_HORIZON):
        arr = np.array(history)
        r7 = arr[-7:].mean() if len(arr) >= 7 else arr.mean()
        r30 = arr[-30:].mean() if len(arr) >= 30 else arr.mean()
        l7 = arr[-7] if len(arr) >= 7 else arr[0]
        l14 = arr[-14] if len(arr) >= 14 else arr[0]
        vel = float(np.polyfit(range(min(14, len(arr))), arr[-min(14, len(arr)):], 1)[0])
        target_dt = today + pd.Timedelta(days=day + 1)
        stock_ratio = r7 / max(1, item_df["reorder_point"].iloc[0])

        numeric_features = [
            r7, r30, l7, l14,
            target_dt.dayofweek, target_dt.month,
            vel, stock_ratio,
            item_df["avg_lead_time_days"].iloc[0],
            item_df["reliability_score"].iloc[0],
        ]
        features = np.array([numeric_features + cat_values])

        pred = float(max(0, catboost.predict(features)[0]))
        forecast.append({
            "date": target_dt.strftime("%Y-%m-%d"),
            "predicted": round(pred, 1),
            "lower": round(max(0, pred * 0.80), 1),
            "upper": round(pred * 1.20, 1),
        })
        history.append(pred)

    return {
        "item_id": item_id,
        "item_name": item_df["item_name"].iloc[0] if "item_name" in item_df else str(item_id),
        "forecast": forecast,
        "model": "CatBoost",
        "r2": meta["catboost"]["r2"],
    }
