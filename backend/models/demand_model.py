"""
Demand Forecasting Model

Models:
    1. Linear Regression (baseline)
    2. ARIMA (time-series baseline)
    3. LightGBM Regressor (primary model)

Metrics: MAE, RMSE, R²
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

try:
    from statsmodels.tsa.arima.model import ARIMA
    ARIMA_AVAILABLE = True
except ImportError:
    ARIMA_AVAILABLE = False

from config import PKL_DIR, RANDOM_SEED, FORECAST_HORIZON
from models.lightgbm_model import (
    build_model as build_lgbm_model,
    cross_validate_r2,
    load_model as load_lgbm_model,
    save_model as save_lgbm_model,
)

FEATURE_COLS = [
    "rolling_7d", "rolling_30d", "lag_7", "lag_14",
    "day_of_week", "month", "velocity", "stock_ratio",
    "avg_lead_time_days", "reliability_score",
]
TARGET_COL = "quantity_used"

PKL_LGBM = PKL_DIR / "demand_lgbm.pkl"
PKL_LR  = PKL_DIR / "demand_lr.pkl"
PKL_META = PKL_DIR / "demand_meta.pkl"


# ─── Training ────────────────────────────────────────────────────────────────

def train(feat_df: pd.DataFrame) -> dict:
    """Train all three demand models. Returns metrics dict."""
    feat_df = feat_df.dropna(subset=FEATURE_COLS + [TARGET_COL])
    X = feat_df[FEATURE_COLS].values
    y = feat_df[TARGET_COL].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, shuffle=False
    )

    # ── LightGBM ─────────────────────────────────────────────────────────────
    lgbm = build_lgbm_model(RANDOM_SEED)
    lgbm.fit(X_train, y_train)
    y_pred_lgbm = lgbm.predict(X_test)

    mae_lgbm  = float(mean_absolute_error(y_test, y_pred_lgbm))
    rmse_lgbm = float(np.sqrt(mean_squared_error(y_test, y_pred_lgbm)))
    r2_lgbm   = float(r2_score(y_test, y_pred_lgbm))
    cv_r2_scores = cross_validate_r2(X_train, y_train, RANDOM_SEED, folds=5)

    save_lgbm_model(lgbm, PKL_LGBM)

    # ── Linear Regression ────────────────────────────────────────────────────
    lr = LinearRegression()
    lr.fit(X_train, y_train)
    y_pred_lr = lr.predict(X_test)

    mae_lr  = float(mean_absolute_error(y_test, y_pred_lr))
    rmse_lr = float(np.sqrt(mean_squared_error(y_test, y_pred_lr)))
    r2_lr   = float(r2_score(y_test, y_pred_lr))

    with open(PKL_LR, "wb") as f:
        pickle.dump(lr, f)

    # ── ARIMA (on first item's time series) ──────────────────────────────────
    mae_arima = rmse_arima = r2_arima = None
    if ARIMA_AVAILABLE:
        try:
            first_item = feat_df.groupby("item_id").first().index[0]
            ts = (
                feat_df[feat_df["item_id"] == first_item]
                .sort_values("usage_date")["quantity_used"]
                .values
            )
            split = int(len(ts) * 0.8)
            model = ARIMA(ts[:split], order=(2, 1, 2))
            res   = model.fit()
            y_ar  = res.forecast(len(ts) - split)
            mae_arima  = float(mean_absolute_error(ts[split:], y_ar))
            rmse_arima = float(np.sqrt(mean_squared_error(ts[split:], y_ar)))
            # ARIMA r2 can be negative; clip for display
            r2_arima   = float(r2_score(ts[split:], y_ar))
        except Exception:
            pass

    # ── Feature importance ───────────────────────────────────────────────────
    importance = [
        {"feature": col, "importance": float(imp)}
        for col, imp in zip(FEATURE_COLS, lgbm.feature_importances_)
    ]
    importance.sort(key=lambda x: x["importance"], reverse=True)

    meta = {
        # Keep xgb key for backward compatibility with existing frontend types.
        "xgb": {"mae": mae_lgbm,  "rmse": rmse_lgbm,  "r2": r2_lgbm},
        "lgbm": {
            "mae": mae_lgbm,
            "rmse": rmse_lgbm,
            "r2": r2_lgbm,
            "cv_r2_scores": cv_r2_scores,
            "cv_r2_mean": float(np.mean(cv_r2_scores)) if cv_r2_scores else None,
        },
        "lr":  {"mae": mae_lr,   "rmse": rmse_lr,    "r2": r2_lr},
        "arima": {"mae": mae_arima, "rmse": rmse_arima, "r2": r2_arima},
        "feature_importance": importance,
        "feature_cols": FEATURE_COLS,
        "primary_model": "LightGBM",
    }
    with open(PKL_META, "wb") as f:
        pickle.dump(meta, f)

    print(f"[DemandModel] LGBM MAE={mae_lgbm:.2f}  RMSE={rmse_lgbm:.2f}  R²={r2_lgbm:.3f}")
    return meta


# ─── Inference ───────────────────────────────────────────────────────────────

def _load_lgbm():
    return load_lgbm_model(PKL_LGBM)


def _load_meta() -> dict:
    with open(PKL_META, "rb") as f:
        return pickle.load(f)


def is_trained() -> bool:
    return PKL_LGBM.exists() and PKL_META.exists()


def predict_forecast(feat_df: pd.DataFrame, item_id: int) -> dict:
    """
    Generate a 14-day demand forecast for a specific item.
    Uses XGBoost iteratively with rolling feature updates.
    """
    lgbm = _load_lgbm()
    meta = _load_meta()

    item_df = (
        feat_df[feat_df["item_id"] == item_id]
        .sort_values("usage_date")
        .tail(60)
        .reset_index(drop=True)
    )

    if item_df.empty:
        return {"error": "No data for this item"}

    # Seed forecast from last known state
    history   = list(item_df["quantity_used"].values)
    forecast  = []
    today     = pd.Timestamp.today().normalize()

    for day in range(FORECAST_HORIZON):
        arr = np.array(history)
        r7  = arr[-7:].mean()  if len(arr) >= 7  else arr.mean()
        r30 = arr[-30:].mean() if len(arr) >= 30 else arr.mean()
        l7  = arr[-7]          if len(arr) >= 7  else arr[0]
        l14 = arr[-14]         if len(arr) >= 14 else arr[0]
        vel = float(np.polyfit(range(min(14, len(arr))), arr[-min(14,len(arr)):], 1)[0])
        target_dt  = today + pd.Timedelta(days=day + 1)
        stock_ratio = r7 / max(1, item_df["reorder_point"].iloc[0])
        features = np.array([[
            r7, r30, l7, l14,
            target_dt.dayofweek, target_dt.month,
            vel, stock_ratio,
            item_df["avg_lead_time_days"].iloc[0],
            item_df["reliability_score"].iloc[0],
        ]])
        pred = float(max(0, lgbm.predict(features)[0]))
        forecast.append({
            "date": target_dt.strftime("%Y-%m-%d"),
            "predicted": round(pred, 1),
            "lower":     round(max(0, pred * 0.80), 1),
            "upper":     round(pred * 1.20, 1),
        })
        history.append(pred)

    return {
        "item_id":   item_id,
        "item_name": item_df["item_name"].iloc[0] if "item_name" in item_df else str(item_id),
        "forecast":  forecast,
        "metrics":   meta,
        "feature_importance": meta["feature_importance"],
    }
